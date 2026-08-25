import os
import pytest
from fastapi.testclient import TestClient
import json
import uuid
import requests
from unittest.mock import patch, MagicMock


os.environ["FAGE_ENV"] = "test"
os.environ["FAGE_JWT_SECRET"] = "fage-dev-jwt-secret-change-in-production"

from app.main import app
from app.auth import create_access_token
from app.services.llm import call_nvidia_llm

client = TestClient(app)





def test_unauthenticated_api_request():
    response = client.get("/api/dashboard")
    assert response.status_code == 401
    assert "Authentication required" in response.text or "Not authenticated" in response.text

def test_valid_jwt_authorized():
    token = create_access_token(data={"sub": "admin", "role": "admin"})
    response = client.get("/api/dashboard", headers={"Authorization": f"Bearer {token}"})
    
    assert response.status_code == 200

def test_invalid_jwt():
    response = client.get("/api/dashboard", headers={"Authorization": "Bearer invalid.token.here"})
    assert response.status_code == 401

def test_tampered_jwt():
    token = create_access_token(data={"sub": "admin", "role": "admin"})
    
    parts = token.split(".")
    tampered_token = f"{parts[0]}.{parts[1]}.{parts[2][:-5]}abcde"
    response = client.get("/api/dashboard", headers={"Authorization": f"Bearer {tampered_token}"})
    assert response.status_code == 401

def test_old_demo_api_key():
    response = client.get("/api/dashboard", headers={"x-api-key": "fage-demo-key"})
    assert response.status_code == 401

def test_production_missing_jwt_secret():
    
    with patch.dict(os.environ, {"FAGE_ENV": "production", "FAGE_JWT_SECRET": ""}):
        import importlib
        import app.auth
        with patch('logging.Logger.warning') as mock_warning:
            importlib.reload(app.auth)
            
            assert len(app.auth.SECRET_KEY) == 43
            assert app.auth.SECRET_KEY != "fage-dev-jwt-secret-change-in-production"
            mock_warning.assert_any_call(
                "SECURITY WARNING: FAGE_JWT_SECRET is missing or set to the insecure default in a production environment! "
                "Generating a random ephemeral secret. All user sessions will be invalidated on server restart."
            )
    
    importlib.reload(app.auth)

def test_production_default_jwt_secret():
    with patch.dict(os.environ, {"FAGE_ENV": "production", "FAGE_JWT_SECRET": "fage-dev-jwt-secret-change-in-production"}):
        import importlib
        import app.auth
        with patch('logging.Logger.warning') as mock_warning:
            importlib.reload(app.auth)
            assert len(app.auth.SECRET_KEY) == 43
            assert app.auth.SECRET_KEY != "fage-dev-jwt-secret-change-in-production"
            mock_warning.assert_any_call(
                "SECURITY WARNING: FAGE_JWT_SECRET is missing or set to the insecure default in a production environment! "
                "Generating a random ephemeral secret. All user sessions will be invalidated on server restart."
            )
    
    importlib.reload(app.auth)





def test_legitimate_static_asset():
    
    response = client.get("/assets/index.js")
    
    assert response.status_code in (200, 404)

def test_legitimate_spa_route():
    response = client.get("/investigation")
    assert response.status_code in (200, 404)

def test_path_outside_static_directory():
    
    response = client.get("/../../../../etc/passwd")
    
    
    assert response.status_code == 200
    assert "<html" in response.text.lower() or "frontend not built" in response.text.lower()

def test_absolute_filesystem_path():
    
    response = client.get("//etc/passwd")
    assert response.status_code == 200
    assert "<html" in response.text.lower() or "frontend not built" in response.text.lower()

def test_traversal_style_path():
    response = client.get("/..%2F..%2F..%2Fetc%2Fpasswd")
    
    assert response.status_code in (200, 403, 404)





def test_llm_timeout_fallback():
    with patch.dict(os.environ, {"NVIDIA_API_KEY": "dummy"}):
        with patch('app.services.guardrails.manager.GuardrailsManager.generate_safe_sar', side_effect=TimeoutError("Timeout")):
            result = call_nvidia_llm("test prompt", fallback="Timeout Fallback")
            assert result == "Timeout Fallback"
            
            result2 = call_nvidia_llm("test prompt")
            assert "Error:" in result2

def test_llm_upstream_5xx_fallback():
    with patch.dict(os.environ, {"NVIDIA_API_KEY": "dummy"}):
        with patch('app.services.guardrails.manager.GuardrailsManager.generate_safe_sar', side_effect=Exception("500 Server Error")):
            result = call_nvidia_llm("test prompt", fallback="500 Fallback")
            assert result == "500 Fallback"
            
            result2 = call_nvidia_llm("test prompt")
            assert "Error:" in result2

def test_llm_missing_api_key_fallback():
    with patch.dict(os.environ, {}, clear=True):
        result = call_nvidia_llm("test prompt", fallback="Missing Key Fallback")
        assert result == "Missing Key Fallback"

def test_llm_api_key_not_in_error_message():
    secret_key = "SECRET_NVIDIA_API_KEY_12345"
    with patch.dict(os.environ, {"NVIDIA_API_KEY": secret_key}):
        with patch('app.services.guardrails.manager.GuardrailsManager.generate_safe_sar', side_effect=Exception(f"Failed with key {secret_key}")):
            result = call_nvidia_llm("test prompt")
            
            assert secret_key not in result
            assert "unexpected error" in result

