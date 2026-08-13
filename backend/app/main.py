import os
import sys
import json
import pickle
import logging
import uuid
import time
import hashlib
from datetime import datetime, UTC
from typing import Dict, List, Any, Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
from pydantic import BaseModel, Field

import threading
import asyncio
import io
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, status, Depends, UploadFile, File, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
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
from fastapi.concurrency import run_in_threadpool
from threading import Lock

# Add parent pathing to python import stream to load custom local ML modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


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
# Pydantic models are still defined here AND re-exported from app.schemas
from app.schemas import *  # noqa: F401,F403 — backward-compat re-export

# Setup Logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("FAGE.API.Backend")

# Indicative INR->USD rate for SAR display only — not a live FX feed. Override via env
# so it can be updated without a code change; still approximate, not transactional-grade.
_INR_USD_RATE = float(os.environ.get("FAGE_INR_USD_RATE", "83.5"))

# Auth is provided by app.auth (JWT + API key). See verify_api_key / get_current_user.

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.auth import SECRET_KEY
    _env = os.environ.get("FAGE_ENV", os.environ.get("ENVIRONMENT", "production")).lower().strip()
    _debug = os.environ.get("FAGE_DEBUG", "false").lower().strip() == "true"
    is_dev = _env in ("dev", "development", "test", "testing", "debug") or _debug

    if not SECRET_KEY or SECRET_KEY == "fage-dev-jwt-secret-change-in-production":
        if not is_dev:
            msg = (
                "CRITICAL SECURITY ERROR: Server booting in non-debug/production environment with missing or default hardcoded FAGE_JWT_SECRET! "
                "Set FAGE_JWT_SECRET environment variable to a strong random secret before starting the server."
            )
            logger.critical(msg)
            raise RuntimeError(msg)
        else:
            logger.warning(
                "SECURITY WARNING: Running with missing or default hardcoded FAGE_JWT_SECRET. "
                "This is permitted only in development/testing mode."
            )
    yield

# Initialize FastAPI App representing FAGE (Fraud Analytics & Governance Engine)
app = FastAPI(
    title="FAGE: Fraud Analytics & Governance Engine API",
    description="Prototype-grade back-end decisioning and explainability matrix for high-dimensional mule account identification.",
    version="1.0.0",
    lifespan=lifespan
)


@app.exception_handler(RequestValidationError)
async def _consistent_validation_error_handler(request: Request, exc: RequestValidationError):
    """
    Every deliberate HTTPException in this API already returns {"detail": "<string>"}.
    FastAPI's default handler for Pydantic validation errors instead returns
    {"detail": [<list of structured error objects>]} -- a different shape for the same
    "detail" key. This reconciles the two: "detail" is always a human-readable string,
    with the original structured error list preserved under "errors" for anyone (e.g. the
    frontend, or a developer) who wants the full detail. No information is lost, no route
    logic changes, no test currently depends on the old shape (verified before this change).
    """
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", [])[1:]) or "request body"
    summary = f"{field}: {first.get('msg', 'invalid value')}" if first else "Invalid request."
    return JSONResponse(
        status_code=422,
        content={"detail": summary, "errors": exc.errors()},
    )

# Configure CORS Middleware allowing local React dashboard cross-origin calls.
# Overridable via FAGE_CORS_ORIGINS (comma-separated) for real deployments —
# falls back to the same localhost dev origins as before if unset.
_cors_origins_env = os.environ.get("FAGE_CORS_ORIGINS", "").strip()
_cors_origins = (
    [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    if _cors_origins_env
    else ["http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "http://localhost:5173", "http://127.0.0.1:3000"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Baseline security headers on every response. Purely additive — does not
    change status codes, bodies, or routing, so it cannot break existing behavior."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

# Auth is provided by app.auth (JWT + API key). See verify_api_key / get_current_user.

@app.on_event("startup")
async def verify_security_env_on_startup():
    from app.auth import SECRET_KEY
    _env = os.environ.get("FAGE_ENV", os.environ.get("ENVIRONMENT", "production")).lower().strip()
    _debug = os.environ.get("FAGE_DEBUG", "false").lower().strip() == "true"
    is_dev = _env in ("dev", "development", "test", "testing", "debug") or _debug

    if not SECRET_KEY or SECRET_KEY == "fage-dev-jwt-secret-change-in-production":
        if not is_dev:
            msg = (
                "CRITICAL SECURITY ERROR: Server booting in non-debug/production environment with missing or default hardcoded FAGE_JWT_SECRET! "
                "Set FAGE_JWT_SECRET environment variable to a strong random secret before starting the server."
            )
            logger.critical(msg)
            raise RuntimeError(msg)
        else:
            logger.warning(
                "SECURITY WARNING: Running with missing or default hardcoded FAGE_JWT_SECRET. "
                "This is permitted only in development/testing mode."
            )


# METRICS_PATH is deprecated; use _load_active_model_metrics() instead.







# ==========================================
#         Pydantic Request Schemas
# ==========================================

class PredictRequest(BaseModel):
    features: Dict[str, float] = Field(
        ..., 
        description="Key-value mapping of feature designations and quantitative value states."
    )


class RiskScoreRequest(BaseModel):
    transaction_id: Optional[str] = Field(None, max_length=128, description="Unique identification trace string.")
    sender_id: Optional[str] = Field("ACC-1102", max_length=128, description="Initiator transaction ID sequence.")
    receiver_id: Optional[str] = Field("ACC-8839", max_length=128, description="Receiver/Beneficiary account identifier.")
    amount: float = Field(..., ge=0.0, le=1_000_000_000, description="Quantitative value scale of transfer transactional volume.")
    origin_country: str = Field("US", max_length=8, description="Origin country ISO standard 2-digit code.")
    destination_country: str = Field("US", max_length=8, description="Destination country ISO standard 2-digit code.")
    account_age_days: int = Field(365, ge=0, le=100_000, description="Operational age of sending account in calendar days.")
    is_international: bool = Field(False, description="Flag setting geographical cross-border traits.")
    custom_metrics: Optional[Dict[str, float]] = Field(
        None, 
        description="Optional telemetry metrics dictionary corresponding to high-dimensional FAGE model parameters."
    )


class AlertUpdateRequest(BaseModel):
    status: str = Field(..., max_length=32, description="Action state: Open, Investigating, Escalated, Closed.")
    notes: Optional[str] = Field(None, max_length=5000, description="Operational remarks/case ledger inputs.")
    assigned_to: Optional[str] = Field(None, max_length=128, description="Operator assignment name.")
    operator_name: Optional[str] = Field("System Operator", max_length=128, description="Name of the operator making the change.")


class AlertIngestRequest(BaseModel):
    transaction_id: str = Field(..., max_length=128, description="Unique transaction ID.")
    sender_id: Optional[str] = Field("ACC-UNKN", max_length=128, description="Sender account.")
    receiver_id: Optional[str] = Field("ACC-UNKN", max_length=128, description="Receiver account.")
    amount: float = Field(..., ge=0.0, le=1_000_000_000, description="Transaction amount.")
    risk_score: int = Field(..., ge=0, le=100, description="Mule risk score out of 100.")
    severity: Optional[str] = Field(None, max_length=32, description="Severity rating, mapped automatically if null.")
    status: Optional[str] = Field("Open", max_length=32, description="Alert status state: Open, Investigating, Escalated, Closed.")
    reason: Optional[str] = Field("Manual external legacy rule sync ingestion.", max_length=2000, description="Alert rationale.")
    timestamp: Optional[str] = Field(None, max_length=64, description="ISO timestamp string.")
    assigned_to: Optional[str] = Field("Unassigned", max_length=128, description="Operator assignment.")
    logs: Optional[List[Dict[str, Any]]] = Field(None, description="Logs audit trail.")


class SARResponse(BaseModel):
    sar_report: str
    fincen_tracking_id: Optional[str] = None
    citation_hash: Optional[str] = None


class PlainLanguageExplanationResponse(BaseModel):
    explanation: str


class TuneRequest(BaseModel):
    new_threshold: float


class PUCalibrateRequest(BaseModel):
    raw_probabilities: List[float] = Field(..., description="List of raw predicted probabilities P(s=1|x)")
    c_factor: Optional[float] = Field(None, description="Optional override label frequency c")


class SPYTuneRequest(BaseModel):
    spy_threshold: Optional[float] = Field(None, description="New reliable negative SPY threshold (0-1)")
    c_factor: Optional[float] = Field(None, description="New PU discovery probability c factor (0-1)")


class TriageEvalRequest(BaseModel):
    risk_score: float = Field(..., description="Model risk score (0-100)")
    ci_lower: float = Field(..., description="Lower bound of 90% confidence interval (0-1)")
    ci_upper: float = Field(..., description="Upper bound of 90% confidence interval (0-1)")
    evadable: bool = Field(False, description="Whether profile is evadable within 3-feature perturbation")
    pu_probability: Optional[float] = Field(None, description="PU calibrated probability (0-1)")
    account_id: Optional[str] = Field("TXN-EVAL", description="Account identifier")


class FeedbackRequest(BaseModel):
    alert_id: str = Field(..., max_length=128, description="Alert ID or Account ID being reviewed")
    label: str = Field(..., max_length=64, description="Ground truth label: 'True Positive', 'False Positive', 'Mule Ring', 'Suspicious'")
    analyst_notes: Optional[str] = Field(None, max_length=5000, description="Detailed notes on investigation rationale")
    trigger_recalibration: bool = Field(True, description="Whether to trigger online PU and threshold recalibration")
    tenant_id: Optional[str] = Field("TN-GLOBAL-01", max_length=128, description="Tenant ID")
    org_id: Optional[str] = Field("ORG-FIN-PRIMARY", max_length=128, description="Organization ID")


class FeedbackResponse(BaseModel):
    status: str = "success"
    alert_id: str
    label_recorded: str
    recalibration_triggered: bool
    old_c_factor: float
    new_c_factor: float
    old_spy_threshold: Optional[float]
    new_spy_threshold: Optional[float]
    message: str





class DPExportRequest(BaseModel):
    epsilon: Optional[float] = Field(None, gt=0.0, description="Requested privacy epsilon budget")
    mechanism: str = Field("laplace", description="Noise injection mechanism ('laplace' or 'gaussian')")


class DPResetRequest(BaseModel):
    max_epsilon: Optional[float] = Field(None, gt=0.0, description="New maximum epsilon budget to allocate")


# ==========================================
#             API Core Routes
# ==========================================





# In-memory login throttle: 5 failed attempts for the same username within 5 minutes
# locks that username out for 60 seconds. Deliberately generous — this is meant to slow
# down brute-force guessing, not to interfere with normal use or the test suite (which
# only ever sends one bad password before a good one).






# General-purpose in-memory rate limiter for expensive endpoints (model inference, graph
# analytics). Same fixed-window-per-key pattern as the login throttle above, generalized to
# take (max_requests, window_seconds) and key on client IP + route name. No Redis/external
# infra -- a plain dict is sufficient for a single-process demo deployment and matches the
# precedent already set by _check_login_throttle.




























































class AdversarialShiftRequest(BaseModel):
    shift_type: str = Field("micro_structuring", description="Type of distribution shift to simulate.")
    intensity: float = Field(0.6, ge=0.0, le=1.0, description="Shift intensity (0-1).")
    trigger_adaptation: bool = Field(True, description="Whether to allow adaptive recalibration if drift is detected.")



















# ── Router registration (Task 8 split) ────────────────────────────────
from app.routers import system as _router_system
from app.routers import auth as _router_auth
from app.routers import governance as _router_governance
from app.routers import analytics as _router_analytics
from app.routers import inference as _router_inference
app.include_router(_router_system.router)
app.include_router(_router_auth.router)
app.include_router(_router_governance.router)
app.include_router(_router_analytics.router)
app.include_router(_router_inference.router)

# ==========================================
# Unified Deployment
# ==========================================
api_app = app
app = FastAPI(lifespan=lifespan)

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import Request

app.mount("/api", api_app)

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "frontend", "dist")
if os.path.exists(static_dir):
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        static_root = os.path.realpath(static_dir)
        candidate_path = os.path.realpath(os.path.join(static_root, full_path))
        
        if os.path.commonpath([static_root, candidate_path]) != static_root:
            raise HTTPException(status_code=403, detail="Forbidden")

        if full_path and os.path.exists(candidate_path) and os.path.isfile(candidate_path):
            return FileResponse(candidate_path)
            
        index_path = os.path.join(static_root, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="Frontend not built")

if __name__ == "__main__":
    import uvicorn
    print("=== STARTING FASTAPI DEV STREAM ON PORT 8000 ===")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
