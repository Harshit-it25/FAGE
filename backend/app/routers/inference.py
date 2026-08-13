from __future__ import annotations
import os
import sys
import json
import pickle
import logging
import uuid
import time
import hashlib
import threading
import asyncio
import io
import random
from datetime import datetime, UTC, timedelta
from typing import Dict, List, Any, Optional

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from pydantic import BaseModel, Field

from fastapi import APIRouter, FastAPI, HTTPException, Query, status, Depends, UploadFile, File, Request, Header
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from threading import Lock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db import get_db, AlertModel, AuditLogModel, write_audit
from app.auth import (
    verify_api_key,
    authenticate_user,
    create_access_token,
    get_current_user,
    AuthUser,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    TokenResponse,
)
from app.services.risk_engine import FAGERiskEngine
from app.ml.dp_engine import dp_engine, PrivacyBudgetExceededError
from app.services.llm import call_nvidia_llm

from app.dependencies import (
    risk_engine, GLOBAL_DECISION_THRESHOLD, _threshold_lock,
    _COMPLIANCE_RULES,
    _active_alert_score_cutoffs, _load_active_model_metrics,
    _compute_rule_exception_rate, _build_real_sample_df,
    _login_failures, _LOGIN_MAX_ATTEMPTS, _LOGIN_WINDOW_SECONDS, _LOGIN_LOCKOUT_SECONDS,
    _check_login_throttle, _record_login_failure,
    _rate_limit_buckets, _rate_limit_lock, rate_limiter,
    _correlate_cache, _CORRELATE_CACHE_TTL_SECONDS,
)
from app.schemas import (
    PredictRequest, RiskScoreRequest, AlertUpdateRequest, AlertIngestRequest,
    SARResponse, PlainLanguageExplanationResponse, TuneRequest, PUCalibrateRequest,
    SPYTuneRequest, TriageEvalRequest, FeedbackRequest, FeedbackResponse,
    DPExportRequest, DPResetRequest, AdversarialShiftRequest,
)

logger = logging.getLogger("FAGE.API.Backend")
_INR_USD_RATE = float(os.environ.get("FAGE_INR_USD_RATE", "83.5"))

router = APIRouter(tags=["Inference Engine"])

@router.post("/predict", tags=["Inference Engine"], dependencies=[Depends(verify_api_key), Depends(rate_limiter(60, 60, "predict"))])
def predict_fraud_probability(request: PredictRequest):
    if not risk_engine.is_production_ready:
        raise HTTPException(
            status_code=503,
            detail="FAGE ML classifier loading sequence incomplete. Verify models are fully compiled and try again."
        )

    try:
        feat_df = pd.DataFrame([request.features])
        aligned_df = risk_engine.preprocessor.transform(feat_df)
        selected_df = risk_engine.selector.transform(aligned_df)

        prob = float(risk_engine.classifier.predict_proba(selected_df)[0, 1])
        with _threshold_lock:
            threshold = GLOBAL_DECISION_THRESHOLD
        class_label = int(prob >= threshold)

        return {
            "status": "success",
            "metadata": {
                "execution_timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "features_analyzed": selected_df.shape[1]
            },
            "inference": {
                "fraud_probability": prob,
                "predicted_class_label": class_label,
                "decision_threshold": threshold
            }
        }
    except Exception as e:
        logger.error(f"Prediction execution failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Inference Engine execution exception: {str(e)}")

@router.post("/explain", tags=["Inference Engine"], dependencies=[Depends(verify_api_key)])
async def explain_case_attribution(request: PredictRequest, user: AuthUser = Depends(verify_api_key), db: Session = Depends(get_db)):
    if not risk_engine.is_production_ready:
        raise HTTPException(
            status_code=503,
            detail="FAGE ML classifier loading sequence incomplete. Verify models are fully compiled and try again."
        )
    try:
        row_series = pd.Series(request.features)
        
        attributions = await run_in_threadpool(risk_engine.shap_engine.compute_local_shap, row_series)
        waterfall = await run_in_threadpool(risk_engine.shap_engine.generate_waterfall_data, row_series)
        waterfall_b64 = await run_in_threadpool(risk_engine.shap_engine.render_base64_waterfall, row_series)

        write_audit(
            db,
            actor=user.username,
            role=user.role,
            action="alert.explain",
            entity_type="alert",
            entity_id=str(request.features.get("transaction_id", "predict_case")),
            detail="Computed SHAP attribution",
            auth_method=user.auth_method,
        )
        db.commit()

        return {
            "status": "success",
            "attributions": attributions,
            "waterfall_visuals": waterfall,
            "static_chart_base64": waterfall_b64
        }
    except Exception as e:
        logger.error(f"Attribution calculation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Explainability Engine execution error: {str(e)}")

@router.post("/risk-score", tags=["Inference Engine"], dependencies=[Depends(verify_api_key), Depends(rate_limiter(60, 60, "risk-score"))])
def score_and_evaluate_transaction(request: RiskScoreRequest, user: AuthUser = Depends(verify_api_key), db: Session = Depends(get_db)):
    if not risk_engine.is_production_ready:
        raise HTTPException(
            status_code=503,
            detail="FAGE ML classifier loading sequence incomplete. Verify models are fully compiled and try again."
        )
    try:
        payload = request.model_dump()
        if request.custom_metrics:
            for k, v in request.custom_metrics.items():
                payload[k] = v

        scorecard = risk_engine.score_single_case(payload)

        # Priority 1: Natural-language investigation summary, built entirely from the real
        # fields already computed above (no graph_intel here -- that only exists once an alert
        # has been created and /correlate is called against it).
        scorecard["investigation_summary"] = risk_engine.generate_investigation_summary(scorecard, graph_intel=None)
        
        # Gate is anchored to the active model's own cost-optimal threshold (see
        # _active_alert_score_cutoffs docstring) -- a fixed ">= 50" here silently dropped
        # alert creation for almost all real fraud, since real flagged scores cluster near 0-10.
        alert_medium_cutoff, _ = _active_alert_score_cutoffs()
        if scorecard["scores"]["final_risk_score"] >= alert_medium_cutoff:
            existing = db.query(AlertModel).filter(AlertModel.transaction_id == scorecard["transaction_id"]).first()
        
            if not existing:
                alert_id = f"ALT-{str(uuid.uuid4()).upper()}"
                
                reason_summary = scorecard["categorizations"]["alert_severity"] + " Severity Risk Score Card triggered."
                if scorecard["rules_audit"]["triggered_rules_count"] > 0:
                    reasons = [r["reason"] for r in scorecard["rules_audit"]["overrides"]]
                    reason_summary += " Rule Violations detected: " + "; ".join(reasons)
                else:
                    drivers = [d["feature"] for d in scorecard["explainability"]["key_risk_drivers"]]
                    reason_summary += " Driven by high ML features variance: " + ", ".join(drivers)

                logs_trail = [{"operator": "System Agent", "action": "Automatic Risk Score Evaluation", "timestamp": scorecard["timestamp"]}]

                new_alert = AlertModel(
                    id=alert_id,
                    transaction_id=scorecard["transaction_id"],
                    sender_id=request.sender_id,
                    receiver_id=request.receiver_id,
                    amount=request.amount,
                    risk_score=scorecard["scores"]["final_risk_score"],
                    severity=scorecard["categorizations"]["alert_severity"],
                    status="Open",
                    reason=reason_summary,
                    timestamp=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    assigned_to="Unassigned",
                    logs=json.dumps(logs_trail),
                    features=json.dumps(scorecard.get("model_input_features") or payload, default=str),
                    explainability=json.dumps({
                        "key_risk_drivers": scorecard["explainability"]["key_risk_drivers"],
                        "confidence_interval_90": scorecard["scores"].get("confidence_interval_90"),
                        "evasion_resistance": scorecard["explainability"].get("evasion_resistance"),
                    }, default=str),
                    _ts=time.time(),
                    triage_action=(
                        scorecard["categorizations"]["triage_routing"]["triage_action"]
                        if isinstance(scorecard.get("categorizations"), dict) and isinstance(scorecard["categorizations"].get("triage_routing"), dict)
                        else ("FAST_TRACK_FREEZE" if scorecard["scores"]["final_risk_score"] >= _active_alert_score_cutoffs()[1] else ("PRIORITY_MANUAL_REVIEW" if scorecard["scores"]["final_risk_score"] >= alert_medium_cutoff else "STANDARD_MONITORING"))
                    ),
                    priority_tier=(
                        scorecard["categorizations"]["triage_routing"]["priority_tier"]
                        if isinstance(scorecard.get("categorizations"), dict) and isinstance(scorecard["categorizations"].get("triage_routing"), dict)
                        else scorecard["categorizations"]["alert_severity"]
                    ),
                    pu_probability=scorecard["scores"].get("base_ml_probability")
                )
                db.add(new_alert)
                try:
                    # Alert creation is the single most compliance-relevant write this API
                    # performs -- it can recommend account freezes. It previously had NO
                    # corresponding audit log entry. Logged in the SAME transaction as the
                    # alert itself (write_audit adds to the session; committed together below)
                    # so the two can never diverge -- either both persist or neither does.
                    write_audit(
                        db,
                        actor=user.username,
                        role=user.role,
                        action="alert.create",
                        entity_type="alert",
                        entity_id=alert_id,
                        detail=f"Alert created from /risk-score: severity={scorecard['categorizations']['alert_severity']}, "
                               f"score={scorecard['scores']['final_risk_score']}, "
                               f"triage_action={new_alert.triage_action}",
                        auth_method=user.auth_method,
                    )
                    db.commit()
                    scorecard["associated_alert_id"] = alert_id
                    logger.info(f"Generated operational alert incident successfully relative to task: {alert_id}")
                except IntegrityError:
                    # Another concurrent request for the same transaction_id won the insert race.
                    db.rollback()
                    winner = db.query(AlertModel).filter(AlertModel.transaction_id == scorecard["transaction_id"]).first()
                    scorecard["associated_alert_id"] = winner.id if winner else None
                    write_audit(
                        db,
                        actor=user.username,
                        role=user.role,
                        action="alert.create_deduplicated",
                        entity_type="alert",
                        entity_id=winner.id if winner else None,
                        detail=f"Duplicate transaction_id {scorecard['transaction_id']} -- concurrent request already created this alert.",
                        auth_method=user.auth_method,
                    )
                    db.commit()
            else:
                scorecard["associated_alert_id"] = existing.id

        return {
            "status": "success",
            "scorecard": scorecard
        }
    except Exception as e:
        logger.error(f"Transaction review pipeline failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Risk Score Engine execution failure: {str(e)}")

def _process_batch_csv(file_bytes: bytes) -> Dict[str, Any]:
    REQUIRED_COLS = {"amount", "origin_country", "destination_country", "account_age_days", "is_international"}
    results = []
    processed_rows = 0
    errors = []

    for chunk in pd.read_csv(io.BytesIO(file_bytes), chunksize=100):
        if processed_rows > 10000:
            errors.append("Hard cap of 10,000 rows reached. Remaining rows ignored.")
            break

        if processed_rows == 0:
            missing = REQUIRED_COLS - set(chunk.columns)
            if missing:
                raise ValueError(f"CSV missing required columns: {', '.join(missing)}")

        for _, row in chunk.iterrows():
            req_data = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}

            try:
                req_data["amount"] = float(req_data.get("amount") or 0.0)
                req_data["account_age_days"] = int(float(req_data.get("account_age_days") or 0))
                req_data["is_international"] = str(req_data.get("is_international") or "false").lower() in ("true", "1", "yes", "t")

                if req_data.get("custom_metrics") and isinstance(req_data["custom_metrics"], str):
                    try:
                        req_data["custom_metrics"] = json.loads(req_data["custom_metrics"])
                    except Exception:
                        req_data["custom_metrics"] = {}
                elif not isinstance(req_data.get("custom_metrics"), dict):
                    req_data["custom_metrics"] = {}
            except Exception as coerce_e:
                errors.append(f"Row {processed_rows + 1}: type coercion failed - {coerce_e}")
                processed_rows += 1
                continue

            try:
                scorecard = risk_engine.score_single_case(req_data)
                results.append(scorecard)
            except Exception as row_e:
                errors.append(f"Row {processed_rows + 1}: scoring failed - {row_e}")
                results.append({"error": str(row_e), "row_index": processed_rows + 1})
            processed_rows += 1

    return {
        "status": "success",
        "processed_rows": processed_rows,
        "scored_count": len([r for r in results if "error" not in r]),
        "error_count": len(errors),
        "errors": errors[:50],
        "results": results
    }

@router.post("/batch-score", tags=["Inference Engine"], dependencies=[Depends(verify_api_key)])
async def batch_score_transactions(file: UploadFile = File(...), user: AuthUser = Depends(verify_api_key), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
    try:
        content = await file.read()
        results = await run_in_threadpool(_process_batch_csv, content)

        write_audit(
            db,
            actor=user.username,
            role=user.role,
            action="alert.batch_ingest",
            entity_type="alert",
            entity_id=file.filename,
            detail=f"Batch scored {results.get('total_processed', 0)} transactions",
            auth_method=user.auth_method,
        )
        db.commit()

        return results
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch processing error: {str(e)}")

