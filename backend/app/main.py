import os
from dotenv import load_dotenv
load_dotenv()

import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Add parent pathing to python import stream to load custom local ML modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Pydantic models are still defined here AND re-exported from app.schemas
from app.schemas import *  # noqa: F401,F403 — backward-compat re-export

# Setup Logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("FAGE.API.Backend")

# Indicative INR->USD rate for SAR display only — not a live FX feed.
_INR_USD_RATE = float(os.environ.get("FAGE_INR_USD_RATE", "83.5"))

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
    "detail" key. This reconciles the two.
    """
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", [])[1:]) or "request body"
    summary = f"{field}: {first.get('msg', 'invalid value')}" if first else "Invalid request."
    return JSONResponse(
        status_code=422,
        content={"detail": summary, "errors": exc.errors()},
    )

# Configure CORS Middleware
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
    """Baseline security headers on every response."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

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
