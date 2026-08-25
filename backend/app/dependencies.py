from __future__ import annotations
import os
import sys
import json
import logging
import time
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional

import numpy as np
import pandas as pd
from fastapi import HTTPException, Request
from threading import Lock
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db import AlertModel
from app.services.risk_engine import FAGERiskEngine

logger = logging.getLogger("FAGE.API.Backend")
_INR_USD_RATE = float(os.environ.get('FAGE_INR_USD_RATE', '83.5'))


risk_engine = FAGERiskEngine(
    models_dir=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models"),
    override_rules_enabled=True
)

GLOBAL_DECISION_THRESHOLD = 0.50
try:
    model_metadata_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model_metadata.json")
    if os.path.exists(model_metadata_path):
        with open(model_metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        
        xgb_threshold = meta.get("decision_threshold")
        if xgb_threshold is not None:
            GLOBAL_DECISION_THRESHOLD = float(xgb_threshold)
            logger.info(f"Seeded GLOBAL_DECISION_THRESHOLD={GLOBAL_DECISION_THRESHOLD} from model_metadata.json.")
        else:
            logger.warning("model_metadata.json has no 'decision_threshold' key — using default 0.50.")
    else:
        logger.warning("model_metadata.json unavailable. Using safe default 0.50.")
except Exception as e:
    logger.warning(f"Failed to load canonical threshold from model_metadata.json: {e}")

_threshold_lock = Lock()

def get_global_threshold() -> float:
    """Thread-safe getter for the global decision threshold.
    Use this instead of reading GLOBAL_DECISION_THRESHOLD directly when the
    value may have been updated at runtime via /tune-threshold.
    """
    with _threshold_lock:
        return GLOBAL_DECISION_THRESHOLD

def set_global_threshold(new_value: float) -> None:
    """Thread-safe setter for the global decision threshold.
    This must be the only mutation point so every module reading via
    get_global_threshold() sees the updated value immediately.
    """
    global GLOBAL_DECISION_THRESHOLD
    with _threshold_lock:
        GLOBAL_DECISION_THRESHOLD = new_value
    logger.info(f"GLOBAL_DECISION_THRESHOLD updated to {new_value}")









_COMPLIANCE_RULES_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "compliance_rules.json"
)
_COMPLIANCE_RULES_DEFAULTS: dict = {
    "sanctioned_countries": ["IR", "KP", "SY", "SD", "CU"],
    "amount_threshold": 150000.0,
    "new_account_max_days": 7.0,
    "new_account_transfer_threshold": 25000.0,
    "structuring_band_min": 9000,
    "structuring_band_max": 9999,
    "high_velocity_threshold": 3,
    "high_velocity_window_hours": 6,
}
_COMPLIANCE_RULES: dict = dict(_COMPLIANCE_RULES_DEFAULTS)
try:
    if os.path.exists(_COMPLIANCE_RULES_PATH):
        with open(_COMPLIANCE_RULES_PATH, "r", encoding="utf-8") as _f:
            _loaded = json.load(_f)
            
            _COMPLIANCE_RULES.update(
                {k: v for k, v in _loaded.items() if not k.startswith("_comment")}
            )
        logger.info("Loaded compliance_rules.json into _COMPLIANCE_RULES (%d keys).", len(_COMPLIANCE_RULES))
    else:
        logger.warning("compliance_rules.json not found — using built-in defaults for all rule thresholds.")
except Exception as _cre:
    logger.error("Failed to load compliance_rules.json: %s — using built-in defaults.", _cre)


_login_failures: Dict[str, List[float]] = {}
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 300
_LOGIN_LOCKOUT_SECONDS = 60

_rate_limit_buckets: Dict[str, List[float]] = {}
_rate_limit_lock = Lock()
# TODO: Move rate limiting and login failures to Redis for horizontal scalability in production

_correlate_cache: Dict[str, tuple] = {}
_correlate_cache_lock = Lock()
_CORRELATE_CACHE_TTL_SECONDS = 30

def get_correlate_cache(alert_id: str) -> Optional[dict]:
    with _correlate_cache_lock:
        cached = _correlate_cache.get(alert_id)
        if cached and (time.time() - cached[0]) < _CORRELATE_CACHE_TTL_SECONDS:
            return cached[1]
    return None

def set_correlate_cache(alert_id: str, result: dict) -> None:
    now = time.time()
    with _correlate_cache_lock:
        stale_keys = [k for k, v in _correlate_cache.items() if now - v[0] >= _CORRELATE_CACHE_TTL_SECONDS]
        for k in stale_keys:
            del _correlate_cache[k]
        _correlate_cache[alert_id] = (now, result)

def _active_alert_score_cutoffs() -> tuple:
    """
    Returns (medium_cutoff, high_cutoff) on the 0-100 score scale, anchored to the ACTIVE
    model's own cost-optimal probability threshold -- not a fixed 50/85 split.

    This exists because that fixed split was found duplicated across three separate call
    sites (alert-creation gate, triage fallback, manual alert endpoint), each silently
    assuming scores spread across 0-100. With a ~0.9% base fraud rate, real cost-optimal
    scores cluster near 0-10 -- so a fixed ">= 50" gate meant the system was not creating
    alert records at all for the large majority of correctly-flagged real fraud. One shared
    function means fixing the assumption once fixes it everywhere, and any future call site
    inherits the correct behavior instead of copying the same wrong constant again.
    """
    active_key = risk_engine.default_model_name.lower() if risk_engine.default_model_name else None
    thr = None
    if active_key and getattr(risk_engine, "per_model_thresholds", None):
        thr = risk_engine.per_model_thresholds.get(active_key)
    if not thr:
        thr = GLOBAL_DECISION_THRESHOLD if GLOBAL_DECISION_THRESHOLD else 0.26
    medium_cutoff = 50.0 * thr
    high_cutoff = 100.0 * thr
    return (medium_cutoff, high_cutoff)

def _load_active_model_metrics() -> dict:
    """Pull metrics for the currently active classifier from the canonical model_metadata.json.

    Key mapping (model_metadata.json → returned dict):
      honest_nested_cv_estimate_15fold_3seed_HEADLINE.precision_mean → precision
      honest_nested_cv_estimate_15fold_3seed_HEADLINE.recall_mean    → recall
      honest_nested_cv_estimate_15fold_3seed_HEADLINE.f1_mean        → f1
      honest_nested_cv_estimate_10fold_2seed.auc                     → roc_auc
      top-level mcc, fpr, brier_score                                → mcc, fpr, brier_score
    """
    try:
        metadata_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model_metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            headline = meta.get("honest_nested_cv_estimate_15fold_3seed_HEADLINE", {})
            cv10 = meta.get("honest_nested_cv_estimate_10fold_2seed", {})
            return {
                "precision": float(headline.get("precision_mean", 0.0)),
                "recall":    float(headline.get("recall_mean", 0.0)),
                "f1":        float(headline.get("f1_mean", 0.0)),
                "roc_auc":   float(cv10.get("auc", 0.0)),
                "fpr":       float(meta.get("fpr", 0.0)),
                "mcc":       float(meta.get("mcc", 0.0)),
                "brier_score": float(meta.get("brier_score", 0.0)),
                "threshold": float(meta.get("threshold", get_global_threshold()))
            }
    except Exception as e:
        logger.error(f"Could not load canonical model metrics: {e}")
    return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "roc_auc": 0.0, "fpr": 0.0, "mcc": 0.0, "brier_score": 0.0, "threshold": get_global_threshold()}

def _compute_rule_exception_rate(db: Session) -> float:
    """
    Real exception rate: fraction of alerts in DB that trigger at
    least one heuristic rule override when re-evaluated against
    risk_engine.evaluate_heuristic_overrides().
    """
    alerts = db.query(AlertModel).all()
    if not alerts:
        return 0.0

    triggered = 0
    for alert in alerts:
        features = json.loads(alert.features) if alert.features else {}
        payload = {
            "amount": alert.amount,
            "origin_country": features.get("origin_country", "US"),
            "destination_country": features.get("destination_country", "US"),
            "account_age_days": features.get("account_age_days", 365),
            "is_international": features.get("is_international", False),
        }
        overrides = risk_engine.evaluate_heuristic_overrides(payload)
        if overrides:
            triggered += 1

    return round(triggered / len(alerts), 4)

def _build_real_sample_df(db: Session, n: int = 10) -> pd.DataFrame:
    """
    Build a DataFrame of REAL feature rows.
    """
    selected_cols = risk_engine.selector.selected_features_
    means = risk_engine.shap_engine.background_means_

    alerts = [a.to_dict() for a in db.query(AlertModel).all()]
    candidates = [a for a in alerts if isinstance(a.get("features"), dict) and a["features"]]

    rows = []
    if candidates:
        import random
        sample = random.sample(candidates, min(n, len(candidates)))
        for alert in sample:
            feat = alert["features"]
            row = {}
            for col in selected_cols:
                try:
                    row[col] = float(feat[col]) if col in feat else float(means.get(col, 0.0))
                except ValueError:
                    row[col] = float(means.get(col, 0.0))
            rows.append(row)

    while len(rows) < n:
        rows.append({col: float(means.get(col, 0.0)) for col in selected_cols})

    return pd.DataFrame(rows)[selected_cols]

def _check_login_throttle(username: str) -> None:
    now = time.time()
    attempts = [t for t in _login_failures.get(username, []) if now - t < _LOGIN_WINDOW_SECONDS]
    _login_failures[username] = attempts
    
    stale_keys = [k for k, v in list(_login_failures.items()) 
                  if k != username and not [t for t in v if now - t < _LOGIN_WINDOW_SECONDS]]
    for k in stale_keys:
        del _login_failures[k]
    if len(attempts) >= _LOGIN_MAX_ATTEMPTS and (now - attempts[0]) < _LOGIN_LOCKOUT_SECONDS:
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts for this account. Try again in a minute.",
        )

def _record_login_failure(username: str) -> None:
    _login_failures.setdefault(username, []).append(time.time())

def rate_limiter(max_requests: int, window_seconds: int, route_name: str):
    """
    Returns a FastAPI dependency enforcing `max_requests` per `window_seconds` per client IP
    for the given route. Raises 429 with a structured, consistent JSON body (see error-handling
    fix below) once the limit is exceeded.
    """
    def _check(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"{route_name}:{client_ip}"
        now = time.time()
        with _rate_limit_lock:
            attempts = [t for t in _rate_limit_buckets.get(key, []) if now - t < window_seconds]
            if len(attempts) >= max_requests:
                retry_after = int(window_seconds - (now - attempts[0])) + 1
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded for this endpoint ({max_requests} requests per "
                           f"{window_seconds}s). Retry after {retry_after}s.",
                    headers={"Retry-After": str(retry_after)},
                )
            attempts.append(now)
            _rate_limit_buckets[key] = attempts
            
            stale_keys = [k for k, v in list(_rate_limit_buckets.items()) if k != key and all(now - t >= window_seconds for t in v)]
            for k in stale_keys:
                del _rate_limit_buckets[k]
    return _check

