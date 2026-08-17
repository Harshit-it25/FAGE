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
from app.services.governance_service import build_sar_report_service, build_explanation_service, build_correlation_graph_service

from fastapi import APIRouter, FastAPI, HTTPException, Query, status, Depends, UploadFile, File, Request, Header
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session, defer
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

router = APIRouter(tags=["Governance"])

@router.get("/dashboard", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
def get_dashboard_summary(db: Session = Depends(get_db)):
    alerts_data = db.query(AlertModel.id, AlertModel.status, AlertModel.risk_score, AlertModel.severity, AlertModel.sender_id, AlertModel.amount).all()
    alerts = [
        {
            "id": a.id,
            "status": a.status,
            "risk_score": a.risk_score,
            "severity": a.severity,
            "sender_id": a.sender_id,
            "amount": a.amount
        }
        for a in alerts_data
    ]
    total_alerts = len(alerts)
    open_alerts = sum(1 for a in alerts if a["status"] == "Open")
    investigating_alerts = sum(1 for a in alerts if a["status"] == "Investigating")
    escalated_alerts = sum(1 for a in alerts if a["status"] == "Escalated")
    closed_alerts = sum(1 for a in alerts if a["status"] == "Closed")

    scores = [a["risk_score"] for a in alerts]
    avg_score = float(np.mean(scores)) if scores else 0.0
    max_score = int(np.max(scores)) if scores else 0
    
    severity_map = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for alert in alerts:
        sev = alert.get("severity", "Medium")
        if sev in severity_map:
            severity_map[sev] += 1
    
    metrics_dict = {}
    active_metrics = _load_active_model_metrics()
    metrics_dict[risk_engine.default_model_name] = active_metrics

    unique_accounts = len({a.get("sender_id") for a in alerts if a.get("sender_id")})
    # Use each alert's own stored severity tier, not a fixed risk_score cutoff. Risk scores are
    # a 0-100 scaling of raw probability, and with a ~0.9% base fraud rate the cost-optimal
    # score range clusters near 0-10, not 50-100 -- a fixed ">= 75" cutoff would silently
    # exclude nearly every real flagged account from "critical_exposure", understating true
    # financial exposure on this dashboard even while those accounts are correctly flagged
    # elsewhere. severity/tier is already computed per-account at the correct, model-relative
    # cutoff (see FAGERiskEngine.map_probability_to_scorecard), so reuse it here instead of
    # re-deriving a second, inconsistent judgment from the raw number.
    critical_alerts = [a for a in alerts if a.get("severity") == "Critical"]
    critical_exposure = float(sum(a.get("amount") or 0 for a in critical_alerts))
    mule_exposure = float(
        sum(
            a.get("amount") or 0
            for a in alerts
            if (a.get("id") or "").startswith("ALT-TGT-") or a.get("severity") in ("Critical", "High")
        )
    )

    active_metrics = _load_active_model_metrics()

    return {
        "status": "success",
        "compiled_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "telemetry": {
            "total_incidents_recorded": total_alerts,
            "unique_accounts_analysed": unique_accounts,
            "critical_alert_count": len(critical_alerts),
            "critical_exposure_amount": critical_exposure,
            "mule_exposure_amount": mule_exposure,
            "average_risk_rating": avg_score,
            "maximum_index_severity": max_score,
            "incident_status_matrix": {
                "Open": open_alerts,
                "Investigating": investigating_alerts,
                "Escalated": escalated_alerts,
                "Closed": closed_alerts
            },
            "severity_profile": severity_map,
            "rule_exception_rate": _compute_rule_exception_rate(db),
            "mule_classification_precision": active_metrics["precision"],
            "mule_classification_recall": active_metrics["recall"],
            "mule_classification_f1": active_metrics["f1"]
        },
        "models": metrics_dict
    }

@router.get("/alerts", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
def list_alerts_queue(
    status_filter: Optional[str] = Query(None, description="Select Alert status: Open, Investigating, Escalated, Closed."),
    severity_filter: Optional[str] = Query(None, description="Select Severity: Low, Medium, High, Critical."),
    limit: int = Query(5000, ge=1, le=10000),
    db: Session = Depends(get_db)
):
    query = db.query(AlertModel).options(defer(AlertModel.features))
    if status_filter:
        query = query.filter(AlertModel.status.ilike(status_filter))
    if severity_filter:
        query = query.filter(AlertModel.severity.ilike(severity_filter))
        
    results = [a.to_dict(exclude_features=True) for a in query.limit(limit).all()]
        
    return {
        "status": "success",
        "alerts_count": len(results),
        "alerts": results
    }

@router.get("/alerts/{alert_id}/features", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
def get_alert_features(alert_id: str, db: Session = Depends(get_db)):
    alert = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=404,
            detail=f"Target alert record matching reference [{alert_id}] could not be found."
        )
    return {
        "status": "success",
        "features": json.loads(alert.features) if alert.features else {}
    }

@router.post("/alerts", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
def ingest_simulated_alert(payload: AlertIngestRequest, db: Session = Depends(get_db)):
    score = payload.risk_score
    _, severity, _ = risk_engine.map_probability_to_scorecard(score / 100.0)

    permitted_states = {"Open", "Investigating", "Escalated", "Closed"}
    status_state = payload.status or "Open"
    if status_state.capitalize() not in permitted_states:
         raise HTTPException(
             status_code=400,
             detail=f"Provided status label of '{status_state}' is not supported. Allowed: {permitted_states}"
         )

    alert_id = f"ALT-{str(uuid.uuid4()).upper()}"
    timestamp_str = payload.timestamp or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    logs_trail = payload.logs if payload.logs is not None else [
        {"operator": "Manual Synchronizer", "action": "Injected Alert", "timestamp": "Now"}
    ]

    new_record = AlertModel(
        id=alert_id,
        transaction_id=payload.transaction_id,
        sender_id=payload.sender_id,
        receiver_id=payload.receiver_id,
        amount=payload.amount,
        risk_score=score,
        severity=payload.severity or severity,
        status=status_state.capitalize(),
        reason=payload.reason,
        timestamp=timestamp_str,
        assigned_to=payload.assigned_to,
        logs=json.dumps(logs_trail),
        features=json.dumps({}),
        _ts=time.time(),
        triage_action="PRIORITY_MANUAL_REVIEW" if score >= _active_alert_score_cutoffs()[0] else "STANDARD_MONITORING",
        priority_tier=payload.severity or severity,
        pu_probability=float(score) / 100.0
    )

    db.add(new_record)
    db.commit()

    return {
        "status": "success",
        "created_alert_id": alert_id
    }

@router.put("/alerts/{alert_id}", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
def update_alert_status_handler(
    alert_id: str,
    payload: AlertUpdateRequest,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    alert = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=404,
            detail=f"Target alert record matching reference [{alert_id}] could not be found."
        )

    permitted_states = {"Open", "Investigating", "Escalated", "Closed"}
    if payload.status.capitalize() not in permitted_states:
        raise HTTPException(
            status_code=400,
            detail=f"Provided status label of '{payload.status}' is not supported. Allowed: {permitted_states}"
        )

    operator = user.display_name or user.username
    old_status = alert.status
    alert.status = payload.status.capitalize()
    
    log_time = datetime.now(UTC).strftime("%H:%M:%S UTC")
    new_logs = json.loads(alert.logs) if alert.logs else []
    
    new_logs.append({
        "operator": operator,
        "action": f"Changed status from {old_status} to {alert.status}",
        "timestamp": log_time
    })

    if payload.notes:
        new_logs.append({
            "operator": operator,
            "action": f"Appended Analyst Note: {payload.notes}",
            "timestamp": log_time
        })

    if payload.assigned_to is not None:
        old_assignee = alert.assigned_to or "Unassigned"
        alert.assigned_to = payload.assigned_to
        new_logs.append({
            "operator": operator,
            "action": f"Reassigned case from {old_assignee} to {payload.assigned_to}",
            "timestamp": log_time
        })
        
    alert.logs = json.dumps(new_logs)
    alert._ts = time.time()

    write_audit(
        db,
        actor=user.username,
        role=user.role,
        action="alert.update",
        entity_type="alert",
        entity_id=alert_id,
        detail=f"status={alert.status}; assigned_to={alert.assigned_to}",
        auth_method=user.auth_method,
    )

    db.commit()

    return {
        "status": "success",
        "message": f"Alert {alert_id} status updated successfully to {alert.status}.",
        "alert": alert.to_dict()
    }

@router.post("/alerts/{alert_id}/sar", response_model=SARResponse, tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
async def generate_sar_report(alert_id: str, user: AuthUser = Depends(verify_api_key), db: Session = Depends(get_db)):
    return await build_sar_report_service(alert_id, user, db, risk_engine)
@router.post("/alerts/{alert_id}/explain-plain-language", response_model=PlainLanguageExplanationResponse, tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
async def generate_plain_language_explanation(alert_id: str, user: AuthUser = Depends(verify_api_key), db: Session = Depends(get_db)):
    return await build_explanation_service(alert_id, user, db, risk_engine)
@router.get("/stream-alerts", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
async def stream_alerts():
    async def event_generator():
        last_seen_ts = time.time()
        from app.db import SessionLocal
        db = SessionLocal()
        try:
            recent_alerts = db.query(AlertModel).order_by(AlertModel._ts.desc()).limit(10).all()
            for alert in reversed(recent_alerts):
                alert_dict = alert.to_dict()
                yield f"data: {json.dumps(alert_dict)}\n\n"
                last_seen_ts = max(last_seen_ts, alert._ts)
        finally:
            db.close()

        counter = 0
        while True:
            await asyncio.sleep(2.5)
            counter += 1
            db = SessionLocal()
            try:
                updated_alerts = db.query(AlertModel).filter(AlertModel._ts > last_seen_ts).all()
                if updated_alerts:
                    for alert in updated_alerts:
                        alert_dict = alert.to_dict()
                        yield f"data: {json.dumps(alert_dict)}\n\n"
                        last_seen_ts = max(last_seen_ts, alert._ts)
                elif counter % 2 == 0:
                    yield ": heartbeat\n\n"
                else:
                    yield ": keep-alive\n\n"
            finally:
                db.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/similar-cases/{alert_id}", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key), Depends(rate_limiter(40, 60, "similar-cases"))])
def similar_cases(alert_id: str, top_n: int = 5, user: AuthUser = Depends(verify_api_key), db: Session = Depends(get_db)):
    """
    Priority 5: Similar Past Cases via real cosine similarity over stored SHAP-driven feature
    vectors -- no new ML, no fabricated case outcomes. Each alert already stores its full
    preprocessed feature vector (AlertModel.features) and its top SHAP drivers
    (AlertModel.explainability); similarity is computed directly over those real numbers.

    IMPORTANT: this only surfaces what's actually in the alerts table. There is no
    "confirmed mule" / "recovered amount" field in the schema -- outcome is reported using the
    real `status` field (Open/Under Review/Closed) rather than inventing investigation results
    that were never recorded.
    """
    target = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
    if not target or not target.features:
        raise HTTPException(status_code=404, detail="Alert not found or has no stored feature vector.")

    try:
        target_features = json.loads(target.features)
    except Exception:
        raise HTTPException(status_code=422, detail="Stored feature vector could not be parsed.")

    candidates = db.query(AlertModel).filter(AlertModel.id != alert_id, AlertModel.features.isnot(None)).all()
    if not candidates:
        return {"target_alert": alert_id, "similar_cases": [], "note": "No other alerts with stored feature vectors exist yet."}

    # Align on the numeric keys common to the target and each candidate. Real preprocessed
    # feature vectors, not embeddings invented for this feature -- same numbers the model
    # itself was scored on.
    common_numeric_keys = sorted([
        k for k, v in target_features.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    ])
    if not common_numeric_keys:
        return {"target_alert": alert_id, "similar_cases": [], "note": "Target alert's feature vector has no numeric fields to compare."}

    target_vec = np.array([float(target_features.get(k, 0.0)) for k in common_numeric_keys]).reshape(1, -1)

    scored = []
    for c in candidates:
        try:
            c_features = json.loads(c.features)
        except Exception:
            continue
        c_vec = np.array([float(c_features.get(k, 0.0)) for k in common_numeric_keys]).reshape(1, -1)
        if not np.any(c_vec):
            continue
        try:
            sim = float(cosine_similarity(target_vec, c_vec)[0, 0])
        except Exception:
            continue
        scored.append((sim, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_n]

    similar_cases_out = []
    for sim, c in top:
        expl = {}
        try:
            expl = json.loads(c.explainability) if c.explainability else {}
        except Exception:
            pass
        similar_cases_out.append({
            "alert_id": c.id,
            "similarity_pct": round(sim * 100, 1),
            "risk_score": c.risk_score,
            "status": c.status,  # real recorded status -- never a fabricated outcome label
            "top_shap_drivers": [d.get("feature") for d in expl.get("key_risk_drivers", [])[:2]],
            "timestamp": c.timestamp
        })

    return {
        "target_alert": alert_id,
        "similar_cases": similar_cases_out,
        "method": "Cosine similarity over real preprocessed feature vectors (same features the model was scored on).",
        "note": "Outcome shown is the real recorded alert status. This system does not track confirmed-fraud "
                "or recovered-amount outcomes, so those are not shown or fabricated."
    }

@router.get("/correlate/{alert_id}", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key), Depends(rate_limiter(40, 60, "correlate"))])
def correlate_alert(alert_id: str, user: AuthUser = Depends(verify_api_key), db: Session = Depends(get_db)):
    return build_correlation_graph_service(alert_id, user, db)
@router.post("/triage-eval", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key), Depends(require_role("admin"))])
async def evaluate_operational_triage(request: TriageEvalRequest):
    if not risk_engine.triage_policy:
        raise HTTPException(status_code=500, detail="Triage policy engine not initialized.")
    result = risk_engine.triage_policy.evaluate_account(
        risk_score=request.risk_score,
        ci_lower=request.ci_lower,
        ci_upper=request.ci_upper,
        evadable=request.evadable,
        pu_probability=request.pu_probability,
        account_id=request.account_id
    )
    return {
        "status": "success",
        "triage_evaluation": result
    }

@router.post("/feedback", response_model=FeedbackResponse, tags=["Model Analytics"], dependencies=[Depends(verify_api_key)])
@router.post("/alerts/{alert_id}/feedback", response_model=FeedbackResponse, tags=["Model Analytics"], dependencies=[Depends(verify_api_key)])
async def submit_analyst_feedback(
    request: FeedbackRequest,
    alert_id: Optional[str] = None,
    user: AuthUser = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    target_alert_id = alert_id or request.alert_id
    if not target_alert_id:
        raise HTTPException(status_code=400, detail="alert_id is required")

    # Check alert in database if present
    alert = db.query(AlertModel).filter(AlertModel.id == target_alert_id).first()
    alert_score = 0.5
    if alert:
        alert_score = (alert.risk_score or 50.0) / 100.0
        if request.label in ["True Positive", "Mule Ring", "Confirmed Fraud"]:
            alert.status = "Escalated"
        elif request.label in ["False Positive", "Legitimate", "Clear"]:
            alert.status = "Closed"

    # Trigger online recalibration if enabled
    old_c = getattr(risk_engine.pu_engine, "c_", 0.725) if risk_engine.pu_engine else 0.725
    new_c = old_c
    old_spy = getattr(risk_engine.pu_engine, "spy_threshold_", 0.152) if risk_engine.pu_engine else 0.152
    new_spy = old_spy

    if request.trigger_recalibration:
        recal = risk_engine.online_recalibrate(label=request.label, alert_score=alert_score)
        old_c = recal.get("old_c_factor", old_c)
        new_c = recal.get("new_c_factor", new_c)
        old_spy = recal.get("old_spy_threshold", old_spy)
        new_spy = recal.get("new_spy_threshold", new_spy)

    write_audit(
        db,
        actor=user.username,
        role=user.role,
        action="alert.feedback_recalibrate" if request.trigger_recalibration else "alert.feedback",
        entity_type="alert_model_closed_loop",
        entity_id=target_alert_id,
        detail=f"Analyst feedback '{request.label}' (notes: {request.analyst_notes or 'None'}). Recalibration: c {old_c:.4f}->{new_c:.4f}, SPY {old_spy}->{new_spy}",
        auth_method=user.auth_method,
        tenant_id=request.tenant_id or "TN-GLOBAL-01",
        org_id=request.org_id or "ORG-FIN-PRIMARY"
    )
    db.commit()

    return FeedbackResponse(
        status="success",
        alert_id=target_alert_id,
        label_recorded=request.label,
        recalibration_triggered=request.trigger_recalibration,
        old_c_factor=old_c,
        new_c_factor=new_c,
        old_spy_threshold=old_spy,
        new_spy_threshold=new_spy,
        message=f"Closed-loop feedback recorded. PU model discovery factor calibrated from {old_c:.4f} to {new_c:.4f}."
    )

