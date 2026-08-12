import os
import sys
import uuid
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.main import api_app as app

client = TestClient(app)


def _login(username: str, password: str) -> dict:
    resp = client.post("/token", data={"username": username, "password": password})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _make_alert(headers: dict) -> str:
    """Create a throwaway alert via the ingest endpoint and return its id."""
    payload = {
        "transaction_id": f"TXN-TEST-{uuid.uuid4().hex[:8].upper()}",
        "sender_id": "ACC-1001",
        "receiver_id": "ACC-2002",
        "amount": 12000.0,
        "risk_score": 90,
    }
    resp = client.post("/alerts", json=payload, headers=headers)
    assert resp.status_code == 200
    return resp.json()["created_alert_id"]


def test_sar_requires_admin_or_auditor_role():
    admin_headers = _login("admin", "admin123")
    analyst_headers = _login("analyst", "analyst123")
    auditor_headers = _login("auditor", "auditor123")

    alert_id = _make_alert(admin_headers)

    denied = client.post(f"/alerts/{alert_id}/sar", headers=analyst_headers)
    assert denied.status_code == 403

    allowed_admin = client.post(f"/alerts/{alert_id}/sar", headers=admin_headers)
    assert allowed_admin.status_code == 200
    assert "sar_report" in allowed_admin.json()
    assert "NOT YET FILED" in allowed_admin.json()["sar_report"]

    allowed_auditor = client.post(f"/alerts/{alert_id}/sar", headers=auditor_headers)
    assert allowed_auditor.status_code == 200


def test_case_log_ignores_client_supplied_operator_name():
    admin_headers = _login("admin", "admin123")
    analyst_headers = _login("analyst", "analyst123")

    alert_id = _make_alert(admin_headers)

    resp = client.put(
        f"/alerts/{alert_id}",
        json={"status": "Investigating", "operator_name": "FAKE_CEO_SPOOF"},
        headers=analyst_headers,
    )
    assert resp.status_code == 200
    latest_log = resp.json()["alert"]["logs"][-1]
    # Attribution must come from the authenticated identity, never the request body.
    assert latest_log["operator"] == "SOC Analyst"
    assert "FAKE_CEO_SPOOF" not in latest_log["operator"]


def test_risk_score_duplicate_transaction_id_does_not_duplicate_alert():
    admin_headers = _login("admin", "admin123")
    txn_id = f"TXN-DUP-{uuid.uuid4().hex[:8].upper()}"
    payload = {
        "transaction_id": txn_id,
        "sender_id": "ACC-3003",
        "receiver_id": "ACC-4004",
        "amount": 15000.0,
        "account_age_days": 2,
        "is_international": True,
    }

    first = client.post("/risk-score", json=payload, headers=admin_headers)
    assert first.status_code == 200

    second = client.post("/risk-score", json=payload, headers=admin_headers)
    assert second.status_code == 200

    # Whether or not the score crossed the alert-worthy threshold, re-scoring the
    # same transaction_id must never raise or silently create a second alert row.
    first_alert_id = first.json()["scorecard"].get("associated_alert_id")
    second_alert_id = second.json()["scorecard"].get("associated_alert_id")
    if first_alert_id is not None:
        assert second_alert_id == first_alert_id
