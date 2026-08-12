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

router = APIRouter(tags=["Authentication"])

@router.post("/token", response_model=TokenResponse, tags=["Authentication"])
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    try:
        _check_login_throttle(form_data.username)
    except HTTPException:
        # Lockout triggered -- this is the most security-relevant login signal (repeated
        # failures in a short window) and previously existed only as a transient in-memory
        # counter, invisible to the permanent audit trail and lost on every restart.
        write_audit(
            db, actor=form_data.username, role=None, action="login_locked_out",
            entity_type="auth", entity_id=form_data.username,
            detail="Login blocked: too many recent failed attempts.", auth_method="jwt",
        )
        db.commit()
        raise

    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        _record_login_failure(form_data.username)
        write_audit(
            db, actor=form_data.username, role=None, action="login_failed",
            entity_type="auth", entity_id=form_data.username,
            detail="Incorrect username or password.", auth_method="jwt",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    _login_failures.pop(form_data.username, None)
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    write_audit(
        db,
        actor=user["username"],
        role=user["role"],
        action="login",
        entity_type="auth",
        entity_id=user["username"],
        detail="Successful password login",
        auth_method="jwt",
    )
    db.commit()
    return TokenResponse(
        access_token=access_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "username": user["username"],
            "role": user["role"],
            "display_name": user["display_name"],
        },
    )

@router.get("/me", tags=["Authentication"], dependencies=[Depends(verify_api_key)])
def read_current_user(user: AuthUser = Depends(get_current_user)):
    return {
        "username": user.username,
        "role": user.role,
        "display_name": user.display_name,
        "auth_method": user.auth_method,
    }

@router.get("/audit-logs", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key), Depends(require_role("admin", "auditor", "service"))])
def list_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    q = db.query(AuditLogModel).order_by(AuditLogModel.id.desc())
    if entity_type:
        q = q.filter(AuditLogModel.entity_type == entity_type)
    if entity_id:
        q = q.filter(AuditLogModel.entity_id == entity_id)
    rows = q.limit(limit).all()
    return {"status": "success", "count": len(rows), "logs": [r.to_dict() for r in rows]}

