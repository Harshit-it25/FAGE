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
from pydantic import BaseModel, Field

from fastapi import APIRouter, BackgroundTasks, FastAPI, HTTPException, Query, status, Depends, UploadFile, File, Request, Header
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import or_
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
from app.services.governance_service import build_sar_report_service, build_explanation_service, build_correlation_graph_service

from app.dependencies import (
    risk_engine,
    _COMPLIANCE_RULES,
    _active_alert_score_cutoffs, _load_active_model_metrics,
    _compute_rule_exception_rate, _build_real_sample_df,
    _login_failures, _LOGIN_MAX_ATTEMPTS, _LOGIN_WINDOW_SECONDS, _LOGIN_LOCKOUT_SECONDS,
    _check_login_throttle, _record_login_failure,
    _rate_limit_buckets, _rate_limit_lock, rate_limiter,
    _correlate_cache, _correlate_cache_lock, _CORRELATE_CACHE_TTL_SECONDS,
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
    alerts = [a.to_dict() for a in db.query(AlertModel).all()]
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
    
    
    
    
    
    
    
    
    total_exposure = float(sum(a.get("amount") or 0 for a in alerts))
    critical_alerts = [a for a in alerts if a.get("severity") == "Critical"]
    critical_exposure = float(sum(a.get("amount") or 0 for a in critical_alerts))
    mule_alerts = [a for a in alerts if (a.get("id") or "").startswith("ALT-TGT-")]
    dataset_alerts = [a for a in alerts if (a.get("id") or "").startswith("ALT-DS-")]
    mule_exposure = float(sum(a.get("amount") or 0 for a in mule_alerts))

    active_metrics = _load_active_model_metrics()

    return {
        "status": "success",
        "compiled_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "telemetry": {
            "total_incidents_recorded": total_alerts,
            "unique_accounts_analysed": unique_accounts,
            "mule_alert_count": len(mule_alerts),
            "dataset_alert_count": len(dataset_alerts),
            "critical_alert_count": len(critical_alerts),
            "total_exposure_amount": total_exposure,
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
    background_tasks: BackgroundTasks,
    status_filter: Optional[str] = Query(None, description="Select Alert status: Open, Investigating, Escalated, Closed."),
    severity_filter: Optional[str] = Query(None, description="Select Severity: Low, Medium, High, Critical."),
    source_filter: Optional[str] = Query(None, description="Filter by data source: all, target, dataset."),
    search: Optional[str] = Query(None, description="Search by alert id, account, or reason."),
    assigned_to: Optional[str] = Query(None, description="Filter by assignee name."),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="Minimum risk score (inclusive)."),
    max_score: Optional[int] = Query(None, ge=0, le=100, description="Maximum risk score (inclusive)."),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(AlertModel)
    if status_filter:
        query = query.filter(AlertModel.status.ilike(status_filter))
    if severity_filter:
        query = query.filter(AlertModel.severity.ilike(severity_filter))
    if source_filter == "target":
        query = query.filter(or_(AlertModel.id.like("ALT-TGT-%"), AlertModel.risk_score >= 60))
    elif source_filter == "dataset":
        query = query.filter(AlertModel.id.like("ALT-DS-%"))
    if assigned_to:
        if assigned_to.lower() == "unassigned":
            query = query.filter(or_(AlertModel.assigned_to.is_(None), AlertModel.assigned_to == "", AlertModel.assigned_to.ilike("unassigned")))
        else:
            query = query.filter(AlertModel.assigned_to.ilike(assigned_to))
    if min_score is not None:
        query = query.filter(AlertModel.risk_score >= min_score)
    if max_score is not None:
        query = query.filter(AlertModel.risk_score <= max_score)
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(
            AlertModel.id.ilike(term),
            AlertModel.sender_id.ilike(term),
            AlertModel.receiver_id.ilike(term),
            AlertModel.reason.ilike(term),
        ))

    total_count = query.count()
    results = [
        a.to_dict()
        for a in query.order_by(AlertModel._ts.desc()).offset(offset).limit(limit).all()
    ]
    slim_results = [{k: v for k, v in a.items() if k != "features"} for a in results]

    from app.services.security_service import security_service
    background_tasks.add_task(security_service.analyze_data_access, user.username, len(results))

    return {
        "status": "success",
        "alerts_count": len(results),
        "total_count": total_count,
        "offset": offset,
        "limit": limit,
        "alerts": slim_results
    }


@router.get("/alerts/{alert_id}", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
def get_alert_by_id(alert_id: str, db: Session = Depends(get_db)):
    alert = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=404,
            detail=f"Target alert record matching reference [{alert_id}] could not be found."
        )
    result = alert.to_dict()
    slim = {k: v for k, v in result.items() if k != "features"}
    return {"status": "success", "alert": slim}

@router.get("/alerts/{alert_id}/features", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
def get_alert_features(alert_id: str, db: Session = Depends(get_db)):
    """Return the raw stored feature vector for a given alert (used by Investigation Workbench)."""
    alert = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=404,
            detail=f"Target alert record matching reference [{alert_id}] could not be found."
        )
    features = json.loads(alert.features) if alert.features else {}
    return {"status": "success", "alert_id": alert_id, "features": features}

@router.post("/alerts", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
def ingest_simulated_alert(payload: AlertIngestRequest, db: Session = Depends(get_db)):
    score = payload.risk_score if payload.risk_score is not None else 0
    _, severity, tier = risk_engine.map_probability_to_scorecard(score / 100.0)

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
        priority_tier=tier,
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
    if payload.status is not None and payload.status.capitalize() not in permitted_states:
        raise HTTPException(
            status_code=400,
            detail=f"Provided status label of '{payload.status}' is not supported. Allowed: {permitted_states}"
        )

    operator = user.display_name or user.username
    log_time = datetime.now(UTC).strftime("%H:%M:%S UTC")
    new_logs = json.loads(alert.logs) if alert.logs else []

    if payload.status is not None:
        old_status = alert.status
        alert.status = payload.status.capitalize()
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
    
    result = alert.to_dict()
    slim = {k: v for k, v in result.items() if k != "features"}

    return {
        "status": "success",
        "message": f"Alert {alert_id} status updated successfully to {alert.status}.",
        "alert": slim
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
            try:
                await asyncio.sleep(2.5)
            except asyncio.CancelledError:
                break
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


@router.get("/correlate/{alert_id}", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key), Depends(rate_limiter(40, 60, "correlate"))])
def correlate_alert(alert_id: str, user: AuthUser = Depends(verify_api_key), db: Session = Depends(get_db)):
    
    
    
    
    
    return build_correlation_graph_service(alert_id, user, db)


@router.post("/triage-eval", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
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

    
    alert = db.query(AlertModel).filter(AlertModel.id == target_alert_id).first()
    alert_score = 0.5
    if alert:
        alert_score = (alert.risk_score or 50.0) / 100.0
        if request.label in ["True Positive", "Mule Ring", "Confirmed Fraud"]:
            alert.status = "Escalated"
        elif request.label in ["False Positive", "Legitimate", "Clear"]:
            alert.status = "Closed"

    
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

