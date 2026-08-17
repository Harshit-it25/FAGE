"""
FAGE authentication: JWT bearer + legacy API-key dual gate.
Demo users are seeded from env; replace with IdP/OIDC for production.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any

from fastapi import Depends, Header, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

import hmac

SECRET_KEY = os.environ.get("FAGE_JWT_SECRET")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("FAGE_JWT_EXPIRE_MINUTES", "480"))

# Single source of truth for "is this a non-production box" — used by every
# dev-only fallback below so they can't disagree with each other.
def _is_dev_env() -> bool:
    _env = os.environ.get("FAGE_ENV", os.environ.get("ENVIRONMENT", "production")).lower().strip()
    _debug = os.environ.get("FAGE_DEBUG", "false").lower() == "true"
    return _env in ("dev", "development", "test", "testing", "debug") or _debug

if not SECRET_KEY or SECRET_KEY == "fage-dev-jwt-secret-change-in-production":
    if not _is_dev_env():
        import secrets
        import logging
        logger = logging.getLogger("FAGE.Auth")
        logger.warning(
            "SECURITY WARNING: FAGE_JWT_SECRET is missing or set to the insecure default in a production environment! "
            "Generating a random ephemeral secret. All user sessions will be invalidated on server restart."
        )
        SECRET_KEY = secrets.token_urlsafe(32)
    else:
        SECRET_KEY = "fage-dev-jwt-secret-change-in-production"

    import warnings
    _auth_logger = logging.getLogger("FAGE.Auth")
    _msg = (
        "\n" + "!" * 78 + "\n"
        "  FAGE_JWT_SECRET is not set or uses the development default.\n"
        "  Running with publicly-known development secret. Anyone can forge a valid\n"
        "  JWT against this deployment. This is permitted ONLY in dev/test.\n"
        "!" * 78
    )
    _auth_logger.warning(_msg)
    warnings.warn(_msg, RuntimeWarning, stacklevel=2)

# Demo/API-key auth completely removed for strict production JWT enforcement.

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

# Demo directory — passwords hashed at import. Override via FAGE_DEMO_USERS JSON later if needed.
_DEMO_PLAIN: Dict[str, Dict[str, str]] = {
    "admin": {"password": "admin123", "role": "admin", "display_name": "Admin (Operator)"},
    "analyst": {"password": "analyst123", "role": "analyst", "display_name": "SOC Analyst"},
    "auditor": {"password": "auditor123", "role": "auditor", "display_name": "Compliance Auditor"},
}

import json as _json

_auth_logger2 = logging.getLogger("FAGE.Auth")

# Demo user store — populated only in non-production environments or when
# FAGE_DEMO_USERS (a JSON object mapping username → {password, role, display_name})
# is explicitly provided as an environment variable.
#
# In production with neither condition met, USERS is intentionally left empty so
# that authenticate_user fails closed — no silent "default password" back-door.
# The existing FAGE_ENV / FAGE_DEBUG check (see _is_dev_env() above) is the single
# source of truth for what constitutes a non-production box.
_fage_demo_users_env = os.environ.get("FAGE_DEMO_USERS", "").strip()
USERS: Dict[str, Dict[str, Any]] = {}

if _fage_demo_users_env:
    try:
        _external_users = _json.loads(_fage_demo_users_env)
        USERS = {
            u: {
                "username": u,
                "hashed_password": pwd_context.hash(m["password"]),
                "role": m["role"],
                "display_name": m["display_name"],
            }
            for u, m in _external_users.items()
        }
        _auth_logger2.info(
            "FAGE.Auth: Loaded %d user(s) from FAGE_DEMO_USERS environment variable.",
            len(USERS),
        )
    except Exception as _ue:
        _auth_logger2.error(
            "FAGE.Auth: Failed to parse FAGE_DEMO_USERS env var: %s. "
            "USERS will be empty — all login attempts will be rejected.",
            _ue,
        )
elif _is_dev_env():
    USERS = {
        username: {
            "username": username,
            "hashed_password": pwd_context.hash(meta["password"]),
            "role": meta["role"],
            "display_name": meta["display_name"],
        }
        for username, meta in _DEMO_PLAIN.items()
    }
    _auth_logger2.warning(
        "FAGE.Auth: Demo accounts (admin/analyst/auditor) loaded because FAGE_ENV=%s. "
        "These credentials MUST NOT be active in a production deployment.",
        os.environ.get("FAGE_ENV", "unset"),
    )
else:
    _auth_logger2.critical(
        "FAGE.Auth: No user store is configured and the runtime environment is not "
        "marked as dev/test. authenticate_user will reject ALL login credentials. "
        "Provide FAGE_DEMO_USERS (JSON) or set FAGE_ENV=dev to configure accounts."
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, str]


class AuthUser(BaseModel):
    username: str
    role: str
    display_name: str
    auth_method: str  # "jwt" | "api_key"


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Verify a plaintext password against the hashed USERS store.

    Returns the user dict on success, or None on failure.

    Fails closed: if USERS is empty (production with no user store configured),
    this function always returns None regardless of the credentials supplied.
    No exception is raised — callers are expected to translate None into a 401.
    """
    user = USERS.get(username)
    if not user or not verify_password(password, user["hashed_password"]):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


def _user_from_payload(payload: dict) -> AuthUser:
    username = payload.get("sub")
    if not username or username not in USERS:
        raise HTTPException(status_code=401, detail="Invalid token subject")
    u = USERS[username]
    return AuthUser(
        username=u["username"],
        role=u["role"],
        display_name=u["display_name"],
        auth_method="jwt",
    )


async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
    bearer: Optional[str] = Depends(oauth2_scheme),
    # SSE/EventSource cannot set custom headers in the browser, so the JWT must travel
    # as ?token=<jwt> in the URL instead. Risk: the token is visible in server access logs,
    # browser history, and transparent proxy caches. Mitigations: keep ACCESS_TOKEN_EXPIRE_MINUTES
    # short (default 480 min — reduce for production), and treat this param as SSE-only.
    token: Optional[str] = Query(None),
) -> AuthUser:
    """Resolve a caller's identity from whichever auth material is present.

    Accepted credential forms (in priority order):
    - ``Authorization: Bearer <jwt>`` header (standard, preferred)
    - ``oauth2_scheme`` bearer extracted by FastAPI's OAuth2 helper
    - ``?token=<jwt>`` query parameter (SSE/EventSource fallback only — see comment above)

    Raises HTTP 401 if no valid credential is found.
    """
    jwt_candidate = bearer or token
    if not jwt_candidate and authorization and authorization.lower().startswith("bearer "):
        jwt_candidate = authorization.split(" ", 1)[1].strip()

    if jwt_candidate:
        try:
            payload = decode_token(jwt_candidate)
            return _user_from_payload(payload)
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired access token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide Bearer JWT.",
        headers={"WWW-Authenticate": "Bearer"},
    )


# Backward-compatible alias used by existing route dependencies
# Backward-compatible alias used by existing route dependencies
async def verify_api_key(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
    bearer: Optional[str] = Depends(oauth2_scheme),
    token: Optional[str] = Query(None),
) -> AuthUser:
    return await get_current_user(authorization, x_api_key, bearer, token)

def require_role(*allowed_roles: str):
    async def _check(user: AuthUser = Depends(verify_api_key)) -> AuthUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of roles: {', '.join(allowed_roles)}. "
                       f"Your role: {user.role}.",
            )
        return user
    return _check
