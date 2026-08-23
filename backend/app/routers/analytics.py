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
from fastapi import APIRouter, FastAPI, HTTPException, Query, status, Depends, Request, Header
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from threading import Lock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db import get_db, AlertModel, AuditLogModel, write_audit
from app.auth import (
    require_role,
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

from app.dependencies import (
    risk_engine,
    set_global_threshold, get_global_threshold,
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

router = APIRouter(tags=["Analytics"])

def _load_confusion_matrix_from_cost_thresholds() -> list:
    """Load confusion matrix from the Conservative operating point in cost_thresholds.json.
    Returns [[TN, FP], [FN, TP]] on success, or a clearly-labelled placeholder on failure.
    """
    try:
        ct_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "cost_thresholds.json")
        ct_path = os.path.realpath(ct_path)
        if os.path.exists(ct_path):
            with open(ct_path, "r", encoding="utf-8") as f:
                ct = json.load(f)
            m = ct.get("operating_points", {}).get("Conservative", {}).get("metrics", {})
            tp = int(m.get("tp", 0))
            fp = int(m.get("fp", 0))
            tn = int(m.get("tn", 0))
            fn = int(m.get("fn", 0))
            return [[tn, fp], [fn, tp]]
    except Exception as e:
        logger.error(f"Failed to load confusion matrix from cost_thresholds.json: {e}")
    return [[0, 0], [0, 0]]  

@router.get("/model-registry", tags=["Model Analytics"], dependencies=[Depends(verify_api_key)])
async def get_model_rejection_registry():
    registry_path = os.path.join(os.path.dirname(__file__), "..", "model_rejection_registry.json")
    registry = {}
    if os.path.exists(registry_path):
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
        except Exception as e:
            logger.error(f"Could not load model rejection registry: {e}")
    metadata_path = os.path.join(os.path.dirname(__file__), "..", "model_metadata.json")
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if isinstance(registry, dict):
                registry["canonical_metadata"] = meta
        except Exception as e:
            logger.error(f"Could not load canonical metadata: {e}")
    return registry

@router.get("/metrics", tags=["Model Analytics"], dependencies=[Depends(verify_api_key)])
async def get_model_metrics_endpoint():
    active_metrics = _load_active_model_metrics()
    model_key = risk_engine.default_model_name
    
    metrics_dict = {
        model_key: {
            "precision": active_metrics["precision"],
            "recall": active_metrics["recall"],
            "f1": active_metrics["f1"],
            "accuracy": active_metrics.get("accuracy", 0.0),
            "threshold": active_metrics["threshold"],
            "fpr": active_metrics.get("fpr", 0.0),
            "mcc": active_metrics.get("mcc", 0.0),
            "brier_score": active_metrics.get("brier_score", 0.0),
            
            
            "confusion_matrix": _load_confusion_matrix_from_cost_thresholds()
        }
    }

    return {
        "source": "backend_metrics_registry",
        "models": metrics_dict
    }

@router.get("/metrics/dp", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
@router.post("/metrics/dp", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
async def get_dp_model_metrics_endpoint(
    epsilon: Optional[float] = Query(None),
    mechanism: str = Query("laplace"),
    request_body: Optional[DPExportRequest] = None,
    user: AuthUser = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """
    Returns model metrics with calibrated ε-Differential Privacy (Laplace or Gaussian) noise injected.
    Consumes privacy budget from the ledger and blocks queries if budget is exhausted.
    """
    eps = epsilon
    mech = mechanism
    if request_body:
        if request_body.epsilon is not None:
            eps = request_body.epsilon
        if request_body.mechanism:
            mech = request_body.mechanism

    active_metrics = _load_active_model_metrics()
    numeric_metrics = {
        "precision": float(active_metrics.get("precision", 0.0)),
        "recall": float(active_metrics.get("recall", 0.0)),
        "f1": float(active_metrics.get("f1", 0.0)),
        "accuracy": float(active_metrics.get("accuracy", 0.0)),
        "threshold": float(active_metrics.get("threshold", 0.0)),
        "fpr": float(active_metrics.get("fpr", 0.0)),
        "mcc": float(active_metrics.get("mcc", 0.0)),
        "brier_score": float(active_metrics.get("brier_score", 0.0))
    }
    
    if risk_engine.pu_engine:
        c_val = getattr(risk_engine.pu_engine, "c_", None)
        if c_val is not None:
            numeric_metrics["c_factor"] = float(c_val)
        spy_val = getattr(risk_engine.pu_engine, "spy_threshold_", None)
        if spy_val is not None:
            numeric_metrics["spy_threshold"] = float(spy_val)

    try:
        dp_result = dp_engine.get_dp_model_metrics(numeric_metrics, epsilon=eps, mechanism=mech)
    except PrivacyBudgetExceededError as e:
        write_audit(
            db,
            actor=user.username,
            role=user.role,
            action="model.metrics_dp_export_rejected",
            entity_type="dp_engine",
            entity_id="budget_exhausted",
            detail=str(e),
            auth_method=user.auth_method,
            tenant_id="TN-GLOBAL-01",
            org_id="ORG-FIN-PRIMARY"
        )
        db.commit()
        raise HTTPException(status_code=429, detail=str(e))

    write_audit(
        db,
        actor=user.username,
        role=user.role,
        action="model.metrics_dp_export",
        entity_type="dp_engine",
        entity_id=f"dp_{mech.lower()}",
        detail=f"Exported DP model metrics with epsilon={dp_result['epsilon_cost']}, guarantee={dp_result['privacy_guarantee']}. Remaining budget: {dp_result['budget_status']['remaining_epsilon']}",
        auth_method=user.auth_method,
        tenant_id="TN-GLOBAL-01",
        org_id="ORG-FIN-PRIMARY"
    )
    db.commit()

    return dp_result

@router.get("/export/graph-summary", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
@router.post("/export/graph-summary", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
async def export_dp_graph_summary(
    epsilon: Optional[float] = Query(None),
    mechanism: str = Query("laplace"),
    request_body: Optional[DPExportRequest] = None,
    user: AuthUser = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """
    Exports graph topology summary and re-identification risk metrics (k-anonymity, l-diversity)
    with calibrated ε-DP Laplace/Gaussian noise to prevent linkage attacks during regulator/export sharing.
    """
    eps = epsilon
    mech = mechanism
    if request_body:
        if request_body.epsilon is not None:
            eps = request_body.epsilon
        if request_body.mechanism:
            mech = request_body.mechanism

    alerts = [a.to_dict() for a in db.query(AlertModel).all()]
    node_count = max(10, len({a.get("sender_id") for a in alerts if a.get("sender_id")} | {a.get("receiver_id") for a in alerts if a.get("receiver_id")}))
    edge_count = max(20, len(alerts))
    sender_counts = {}
    for a in alerts:
        s = a.get("sender_id")
        if s:
            sender_counts[s] = sender_counts.get(s, 0) + 1
    max_degree = max(sender_counts.values()) if sender_counts else 5
    structuring_nodes = sum(1 for a in alerts if "STRUCT" in str(a.get("rule_id", "")).upper() or (a.get("amount") and float(a.get("amount", 0)) < 10000))
    total_volume = sum(float(a.get("amount") or 0.0) for a in alerts)

    raw_stats = {
        "node_count": node_count,
        "edge_count": edge_count,
        "max_degree": max_degree,
        "structuring_nodes": structuring_nodes,
        "total_volume_exposed": total_volume
    }

    try:
        dp_graph = dp_engine.get_dp_graph_summary(raw_stats, epsilon=eps, mechanism=mech)
    except PrivacyBudgetExceededError as e:
        write_audit(
            db,
            actor=user.username,
            role=user.role,
            action="model.graph_dp_export_rejected",
            entity_type="dp_engine",
            entity_id="budget_exhausted",
            detail=str(e),
            auth_method=user.auth_method,
            tenant_id="TN-GLOBAL-01",
            org_id="ORG-FIN-PRIMARY"
        )
        db.commit()
        raise HTTPException(status_code=429, detail=str(e))

    write_audit(
        db,
        actor=user.username,
        role=user.role,
        action="model.graph_dp_export",
        entity_type="dp_engine",
        entity_id=f"graph_dp_{mech.lower()}",
        detail=f"Exported DP graph topology with epsilon={dp_graph['epsilon_cost']}, k-anonymity estimate={dp_graph['reidentification_risk_assessment']['k_anonymity_estimate']}. Remaining budget: {dp_graph['budget_status']['remaining_epsilon']}",
        auth_method=user.auth_method,
        tenant_id="TN-GLOBAL-01",
        org_id="ORG-FIN-PRIMARY"
    )
    db.commit()

    return dp_graph

@router.get("/governance/dp-status", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
async def get_dp_governance_status(user: AuthUser = Depends(verify_api_key)):
    """
    Returns current privacy budget consumption, ledger history, and re-identification risk status.
    """
    return {
        "status": "success",
        "budget_status": dp_engine.get_budget_status()
    }

@router.post("/governance/dp-reset", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key), Depends(require_role("admin", "auditor"))])
async def reset_dp_governance_budget(
    request: Optional[DPResetRequest] = None,
    user: AuthUser = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    """
    Resets the differential privacy epsilon budget. Requires admin or auditor role.
    """
    new_max = request.max_epsilon if request else None
    status_dict = dp_engine.reset_budget(new_max)

    write_audit(
        db,
        actor=user.username,
        role=user.role,
        action="governance.dp_budget_reset",
        entity_type="dp_engine",
        entity_id="budget_ledger",
        detail=f"Privacy budget reset by {user.username} (role={user.role}). New max_epsilon: {status_dict['max_epsilon']}",
        auth_method=user.auth_method,
        tenant_id="TN-GLOBAL-01",
        org_id="ORG-FIN-PRIMARY"
    )
    db.commit()

    return {
        "status": "success",
        "message": "Privacy budget successfully reset.",
        "budget_status": status_dict
    }

@router.get("/feature-importance", tags=["Model Analytics"], dependencies=[Depends(verify_api_key)])
async def get_global_feature_importance(db: Session = Depends(get_db)):
    means = risk_engine.shap_engine.background_means_
    real_samples = _build_real_sample_df(db, n=10)
    
    global_shaps = await run_in_threadpool(risk_engine.shap_engine.compute_global_shap, real_samples)
    summary_data = await run_in_threadpool(risk_engine.shap_engine.generate_summary_data, real_samples)
    summary_b64 = await run_in_threadpool(risk_engine.shap_engine.render_base64_summary, real_samples)

    return {
        "status": "success",
        "model_requested": risk_engine.default_model_name,
        "importance_profile": [
            {"feature": feat, "mean_abs_attribution": score}
            for feat, score in list(global_shaps.items())[:15]
        ],
        "beeswarm_scatter": summary_data,
        "static_beeswarm_base64": summary_b64
    }

@router.post("/tune-threshold", tags=["Model Analytics"], dependencies=[Depends(verify_api_key), Depends(require_role("admin"))])
def tune_model_threshold(request: TuneRequest, user: AuthUser = Depends(verify_api_key), db: Session = Depends(get_db)):
    if not (0.0 < request.new_threshold < 1.0):
        raise HTTPException(status_code=400, detail="Threshold must be between 0.0 and 1.0")
    
    
    
    set_global_threshold(request.new_threshold)

    write_audit(
        db,
        actor=user.username,
        role=user.role,
        action="system.threshold_tune",
        entity_type="system",
        entity_id="GLOBAL_DECISION_THRESHOLD",
        detail=f"Adjusted threshold to {request.new_threshold}",
        auth_method=user.auth_method,
    )
    db.commit()

    return {
        "status": "success", 
        "message": f"Global risk threshold adjusted to {request.new_threshold}",
        "new_threshold": request.new_threshold
    }

@router.get("/cost-thresholds", tags=["Model Analytics"], dependencies=[Depends(verify_api_key)])
async def get_cost_thresholds():
    cost_path = os.path.join(os.path.dirname(__file__), "..", "cost_thresholds.json")
    if os.path.exists(cost_path):
        try:
            with open(cost_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data["status"] = "success"
                fin = data.get("financial_parameters", {})
                data.setdefault("c_fn", fin.get("c_fn_mule_loss_inr", 388000.0))
                data.setdefault("c_fp", fin.get("c_fp_audit_cost_inr", 1200.0))
                ops = data.get("operating_points", {})
                cons = ops.get("Conservative", {}) if isinstance(ops, dict) else {}
                data.setdefault("optimal_threshold", cons.get("threshold", 0.65))
            return data
        except Exception as e:
            logger.error(f"Failed to load cost_thresholds.json: {e}")
    if risk_engine.cost_optimizer:
        return {
            "status": "success",
            "c_fn": getattr(risk_engine.cost_optimizer, "c_fn", 388000.0),
            "c_fp": getattr(risk_engine.cost_optimizer, "c_fp", 1200.0),
            "optimal_threshold": getattr(risk_engine.cost_optimizer, "optimal_threshold", 0.50),
            "note": "Loaded from active memory optimizer."
        }
    raise HTTPException(status_code=404, detail="Cost threshold metrics not found.")

@router.get("/pu-calibration", tags=["Model Analytics"], dependencies=[Depends(verify_api_key)])
async def get_pu_calibration_metrics():
    pu_path = os.path.join(os.path.dirname(__file__), "..", "pu_metrics.json")
    if os.path.exists(pu_path):
        try:
            with open(pu_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data["status"] = "success"
                data.setdefault("c_estimate", data.get("overall_c_estimate", 1.0))
                data.setdefault("spy_threshold", data.get("spy_threshold", 0.01))
            return data
        except Exception as e:
            logger.error(f"Failed to load pu_metrics.json: {e}")
    if risk_engine.pu_engine:
        return {
            "status": "success",
            "c_estimate": getattr(risk_engine.pu_engine, "c_", 1.0),
            "spy_threshold": getattr(risk_engine.pu_engine, "spy_threshold_", None),
            "note": "Loaded from active memory PU engine."
        }
    raise HTTPException(status_code=404, detail="PU calibration metrics not found.")

@router.post("/pu-calibration", tags=["Model Analytics"], dependencies=[Depends(verify_api_key), Depends(require_role("admin"))])
async def calibrate_pu_probabilities(request: PUCalibrateRequest, user: AuthUser = Depends(verify_api_key), db: Session = Depends(get_db)):
    if not risk_engine.pu_engine:
        raise HTTPException(status_code=500, detail="PU learning engine not active.")
    probs = np.array(request.raw_probabilities)
    calibrated = risk_engine.pu_engine.calibrate_probabilities(probs, c=request.c_factor)

    write_audit(
        db,
        actor=user.username,
        role=user.role,
        action="system.pu_calibrate",
        entity_type="system",
        entity_id="pu_engine",
        detail=f"Calibrated probabilities with c_factor={request.c_factor}",
        auth_method=user.auth_method,
    )
    db.commit()

    return {
        "status": "success",
        "c_factor_used": request.c_factor if request.c_factor is not None else getattr(risk_engine.pu_engine, "c_", 1.0),
        "raw_probabilities": request.raw_probabilities,
        "calibrated_probabilities": calibrated.tolist()
    }

@router.post("/pu-calibration/tune", tags=["Model Analytics"], dependencies=[Depends(verify_api_key), Depends(require_role("admin"))])
async def tune_pu_calibration(request: SPYTuneRequest, user: AuthUser = Depends(verify_api_key), db: Session = Depends(get_db)):
    if not risk_engine.pu_engine:
        raise HTTPException(status_code=500, detail="PU learning engine not active.")
        
    old_c = getattr(risk_engine.pu_engine, "c_", None) or getattr(risk_engine.pu_engine, "c_estimate_", None) or 0.725
    old_spy = getattr(risk_engine.pu_engine, "spy_threshold_", None) or 0.152
    new_c = request.c_factor if request.c_factor is not None else old_c
    new_spy = request.spy_threshold if request.spy_threshold is not None else old_spy
    
    if request.c_factor is not None:
        risk_engine.pu_engine.c_estimate_ = float(max(0.05, min(1.0, request.c_factor)))
    if request.spy_threshold is not None:
        risk_engine.pu_engine.spy_threshold_ = float(max(0.001, min(0.999, request.spy_threshold)))

    
    try:
        pu_path = os.path.join(risk_engine.models_dir, "pu_engine.pkl")
        os.makedirs(risk_engine.models_dir, exist_ok=True)
        with open(pu_path, "wb") as f:
            pickle.dump(risk_engine.pu_engine, f)
    except Exception as e:
        logger.error(f"Failed to save pu_engine.pkl during SPY tuning: {e}")

    pu_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pu_metrics.json")
    data = {}
    if os.path.exists(pu_json_path):
        try:
            with open(pu_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load pu_metrics.json: {e}")

    data["overall_c_estimate"] = new_c
    data["c_estimate"] = new_c
    if new_spy is not None:
        data["spy_threshold"] = new_spy
        if "spy_statistics" in data and isinstance(data["spy_statistics"], dict):
            data["spy_statistics"]["spy_threshold"] = new_spy
    data["last_tuning_timestamp"] = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        with open(pu_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save pu_metrics.json: {e}")

    old_c_val = float(old_c) if old_c is not None else 0.725
    new_c_val = float(new_c) if new_c is not None else 0.725
    old_spy_val = float(old_spy) if old_spy is not None else 0.152
    new_spy_val = float(new_spy) if new_spy is not None else 0.152

    write_audit(
        db,
        actor=user.username,
        role=user.role,
        action="system.pu_tune",
        entity_type="pu_engine",
        entity_id="SPY_THRESHOLD",
        detail=f"Analyst/Admin tuned PU metrics: c_factor {old_c_val:.4f}->{new_c_val:.4f}, SPY threshold {old_spy_val:.4f}->{new_spy_val:.4f}",
        auth_method=user.auth_method,
    )
    db.commit()

    return {
        "status": "success",
        "old_c_factor": old_c_val,
        "new_c_factor": new_c_val,
        "old_spy_threshold": old_spy_val,
        "new_spy_threshold": new_spy_val,
        "message": "PU calibration metrics successfully tuned."
    }

@router.get("/adversarial-shift/status", tags=["Model Analytics"], dependencies=[Depends(verify_api_key)])
async def get_adversarial_shift_status(
    user: AuthUser = Depends(verify_api_key)
):
    """
    Returns current online drift monitoring metrics (PSI), distribution shift status, and adaptation history.
    """
    status_data = risk_engine.get_adversarial_shift_status()
    return {
        "status": "success",
        "current_shift_status": status_data["current_shift_status"],
        "adaptation_history": status_data["adaptation_history"]
    }

@router.post("/adversarial-shift/simulate", tags=["Model Analytics"], dependencies=[Depends(verify_api_key), Depends(require_role("admin"))])
async def simulate_adversarial_shift_endpoint(
    request: AdversarialShiftRequest,
    user: AuthUser = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """
    Runs an online drift simulation (PSI-based) against the PU calibration engine and,
    if trigger_adaptation is set and drift crosses the adaptation threshold, persists
    recalibrated parameters.
    """
    try:
        result = risk_engine.simulate_adversarial_shift(
            shift_type=request.shift_type, intensity=request.intensity
        )
        if not request.trigger_adaptation:
            result["adaptation_triggered"] = False

        write_audit(
            db,
            actor=user.username,
            role=user.role,
            action="model.adversarial_shift_simulate",
            entity_type="pu_adaptive_engine",
            entity_id=request.shift_type,
            detail=f"intensity={request.intensity}; adaptation_triggered={result.get('adaptation_triggered')}",
            auth_method=user.auth_method,
        )
        db.commit()

        return {"status": "success", "simulation_result": result}
    except Exception as e:
        logger.error(f"Adversarial shift simulation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Adversarial shift simulation error: {str(e)}")

from app.services.mule_similarity import similarity_engine

@router.get("/similar-cases/{alert_id}", tags=["Model Analytics"], dependencies=[Depends(verify_api_key), Depends(rate_limiter(40, 60, "similar-cases"))])
async def get_similar_cases(alert_id: str, top_n: int = Query(5, ge=1, le=50), user: AuthUser = Depends(verify_api_key), db: Session = Depends(get_db)):
    target = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
    if not target or not target.features:
        raise HTTPException(status_code=404, detail="Alert not found or has no stored feature vector.")
        
    try:
        target_features = json.loads(target.features)
    except Exception:
        raise HTTPException(status_code=422, detail="Stored feature vector could not be parsed.")
        
    similar_cases_out = similarity_engine.find_similar(target_features, top_n=top_n, exclude_id=alert_id)
    
    if not similar_cases_out:
        return {"target_alert": alert_id, "similar_cases": [], "note": "No similar cases found in precomputed matrix."}
        
    return {
        "target_alert": alert_id,
        "similar_cases": similar_cases_out
    }

@router.get("/bias-audit", tags=["Model Analytics"], dependencies=[Depends(verify_api_key)])
async def get_bias_audit():
    
    audit_path = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bias_audit.json"))
    if os.path.exists(audit_path):
        try:
            with open(audit_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load bias_audit.json: {e}")
            raise HTTPException(status_code=500, detail="Failed to parse bias audit.")
    raise HTTPException(status_code=404, detail="Bias audit not found.")


