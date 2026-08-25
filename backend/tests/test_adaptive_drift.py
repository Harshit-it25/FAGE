import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.main import app as app


client = TestClient(app, base_url="http://testserver/api")
def get_jwt(client):
    res = client.post("/token", data={"username": "admin", "password": "admin123"})
    return res.json()["access_token"]

def test_get_adversarial_shift_status():
    headers = {"Authorization": f"Bearer {get_jwt(client)}"}
    response = client.get(
        "/adversarial-shift/status",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "current_shift_status" in data
    assert "adaptation_history" in data
    assert data["current_shift_status"]["status"] in ["Stable", "Moderate Drift Detected", "Critical Drift Detected", "Critical Drift", "Moderate Drift"]

def test_simulate_adversarial_shift_micro_structuring():
    payload = {
        "shift_type": "micro_structuring",
        "intensity": 0.85,
        "trigger_adaptation": True
    }
    headers = {"Authorization": f"Bearer {get_jwt(client)}"}
    response = client.post(
        "/adversarial-shift/simulate",
        json=payload,
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    sim_res = data["simulation_result"]
    assert sim_res["shift_type"] == "micro_structuring"
    assert sim_res["adaptation_triggered"] is True
    assert sim_res["overall_psi"] > 0.10
    assert "psi_summary" in sim_res
    assert "pre_adaptation_metrics" in sim_res
    assert "post_adaptation_metrics" in sim_res

def test_simulate_adversarial_shift_dormant_mules():
    payload = {
        "shift_type": "dormant_mule_ring",
        "intensity": 0.75,
        "trigger_adaptation": True
    }
    headers = {"Authorization": f"Bearer {get_jwt(client)}"}
    response = client.post(
        "/adversarial-shift/simulate",
        json=payload,
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    sim_res = data["simulation_result"]
    assert sim_res["shift_type"] == "dormant_mule_ring"
    assert "psi_summary" in sim_res

def test_verify_audit_log_for_adaptive_shift():
    headers = {"Authorization": f"Bearer {get_jwt(client)}"}
    
    # Pre-populate audit log to avoid test ordering dependencies
    payload = {
        "shift_type": "micro_structuring",
        "intensity": 0.85,
        "trigger_adaptation": True
    }
    client.post("/adversarial-shift/simulate", json=payload, headers=headers)

    response = client.get(
        "/audit-logs?entity_type=pu_adaptive_engine",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["logs"]) > 0
    latest = data["logs"][0]
    assert latest["action"] == "model.adversarial_shift_simulate"

