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

router = APIRouter(tags=["System"])

@router.get("/", tags=["System"])
def index():
    return {
        "engine": "FAGE (Fraud Analytics & Governance Engine)",
        "status": "online",
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_loaded": risk_engine.default_model_name,
        "is_fallback_active": not risk_engine.is_production_ready
    }

@router.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "service": "fage-backend",
        "version": "2.0.0",
        "model_ready": risk_engine.is_production_ready
    }

@router.get("/config", tags=["System"])
def get_config():
    medium_cutoff, high_cutoff = _active_alert_score_cutoffs()
    return {
        "medium_cutoff": medium_cutoff,
        "high_cutoff": high_cutoff
    }

