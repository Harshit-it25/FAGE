"""
JWT security verification: expiry, tampering, malformed tokens, wrong-secret forgery,
and role enforcement. Added because existing coverage (test_api.py) verified missing-token
and wrong-password cases, but not the cryptographic attack surface directly.
"""
from datetime import datetime, timedelta, UTC

from fastapi.testclient import TestClient
from jose import jwt

from app.main import api_app as app
from app.auth import SECRET_KEY, ALGORITHM

client = TestClient(app)


def _protected_call(token: str):
    return client.get("/dashboard", headers={"Authorization": f"Bearer {token}"})


def test_expired_token_rejected():
    expired = jwt.encode(
        {"sub": "admin", "role": "admin", "exp": datetime.now(UTC) - timedelta(minutes=5)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    resp = _protected_call(expired)
    assert resp.status_code == 401
    assert "detail" in resp.json()


def test_tampered_payload_rejected():
    # Forge a token with the CORRECT secret but then flip a character in the signature --
    # simulates an attacker who intercepted a token and tried to modify it.
    valid = jwt.encode(
        {"sub": "analyst", "role": "analyst", "exp": datetime.now(UTC) + timedelta(minutes=30)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    header, payload, signature = valid.split(".")
    
    # Tamper the PAYLOAD, not the signature, because base64 decoding of the signature
    # can sometimes ignore changes to the last character if it doesn't change the underlying bytes.
    # We want to simulate changing the role or sub.
    import base64
    import json
    
    payload_dict = json.loads(base64.urlsafe_b64decode(payload + "==").decode('utf-8'))
    payload_dict['role'] = 'admin'
    tampered_payload = base64.urlsafe_b64encode(json.dumps(payload_dict).encode('utf-8')).decode('utf-8').rstrip("=")
    
    tampered = f"{header}.{tampered_payload}.{signature}"
    resp = _protected_call(tampered)
    assert resp.status_code == 401


def test_forged_with_wrong_secret_rejected():
    # Attacker who does NOT know SECRET_KEY tries to mint their own admin token.
    forged = jwt.encode(
        {"sub": "admin", "role": "admin", "exp": datetime.now(UTC) + timedelta(minutes=30)},
        "attacker-guessed-secret-1234",
        algorithm=ALGORITHM,
    )
    resp = _protected_call(forged)
    assert resp.status_code == 401


def test_malformed_token_rejected():
    for garbage in ["not-a-jwt-at-all", "a.b.c", "", "Bearer Bearer admin"]:
        resp = _protected_call(garbage)
        assert resp.status_code == 401, f"Expected 401 for malformed token {garbage!r}"


def test_valid_signature_unknown_user_rejected():
    # Token is cryptographically valid (correct secret, correct alg, not expired) but the
    # subject doesn't correspond to any real user -- e.g. a user deleted after token issuance.
    ghost = jwt.encode(
        {"sub": "deleted_user_ghost", "role": "admin", "exp": datetime.now(UTC) + timedelta(minutes=30)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    resp = _protected_call(ghost)
    assert resp.status_code == 401


def test_missing_token_rejected():
    resp = client.get("/dashboard")
    assert resp.status_code == 401
    assert "detail" in resp.json()


def test_role_enforcement_analyst_cannot_reach_admin_route():
    analyst = client.post("/token", data={"username": "analyst", "password": "analyst123"})
    assert analyst.status_code == 200
    headers = {"Authorization": f"Bearer {analyst.json()['access_token']}"}
    resp = client.get("/audit-logs", headers=headers)
    assert resp.status_code == 403


def test_role_enforcement_admin_can_reach_admin_route():
    admin = client.post("/token", data={"username": "admin", "password": "admin123"})
    assert admin.status_code == 200
    headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
    resp = client.get("/audit-logs", headers=headers)
    assert resp.status_code == 200


def test_valid_token_still_works_after_all_the_above():
    # Sanity check: none of the above accidentally broke normal, legitimate auth.
    ok = client.post("/token", data={"username": "admin", "password": "admin123"})
    assert ok.status_code == 200
    headers = {"Authorization": f"Bearer {ok.json()['access_token']}"}
    resp = client.get("/dashboard", headers=headers)
    assert resp.status_code == 200
def test_rbac_analyst_cannot_tune_threshold():
    analyst = client.post("/token", data={"username": "analyst", "password": "analyst123"})
    assert analyst.status_code == 200
    headers = {"Authorization": f"Bearer {analyst.json()['access_token']}"}
    resp = client.post("/tune-threshold", json={"new_threshold": 0.6}, headers=headers)
    assert resp.status_code == 403

def test_rbac_admin_can_tune_threshold():
    admin = client.post("/token", data={"username": "admin", "password": "admin123"})
    assert admin.status_code == 200
    headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
    resp = client.post("/tune-threshold", json={"new_threshold": 0.6}, headers=headers)
    assert resp.status_code == 200

