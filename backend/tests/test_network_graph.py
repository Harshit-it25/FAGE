import pytest
from fastapi.testclient import TestClient
from app.main import app as app
from app.db import Base, engine, get_db, SessionLocal, AlertModel
from sqlalchemy.orm import sessionmaker

client = TestClient(app, base_url="http://testserver/api")

import uuid
from app.auth import create_access_token

def test_correlate_alert_returns_sender_and_receiver():
    token = create_access_token(data={"sub": "admin", "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}
    
    
    payload1 = {
        "transaction_id": f"TXN-TEST-{uuid.uuid4().hex[:8].upper()}",
        "sender_id": "ACC-TEST-A",
        "receiver_id": "ACC-TEST-B",
        "amount": 10000.0,
        "risk_score": 75,
    }
    resp1 = client.post("/alerts", json=payload1, headers=headers)
    assert resp1.status_code == 200
    alert1_id = resp1.json()["created_alert_id"]
    
    payload2 = {
        "transaction_id": f"TXN-TEST-{uuid.uuid4().hex[:8].upper()}",
        "sender_id": "ACC-TEST-B",
        "receiver_id": "ACC-TEST-C",
        "amount": 5000.0,
        "risk_score": 85,
    }
    resp2 = client.post("/alerts", json=payload2, headers=headers)
    assert resp2.status_code == 200
    alert2_id = resp2.json()["created_alert_id"]

    
    response = client.get(
        f"/correlate/{alert1_id}",
        headers=headers
    )
    if response.status_code != 200:
        print("GET CORRELATE FAILED:", response.status_code, response.text)
    assert response.status_code == 200
    data = response.json()
    
    
    assert data["target_alert"] == alert1_id
    assert data["target_sender"] == "ACC-TEST-A"
    assert data["target_receiver"] == "ACC-TEST-B"
    
    
    related = data["related_entities"]
    assert len(related) > 0
    
    alert2_match = next(a for a in related if a["alert_id"] == alert2_id)
    assert alert2_match["sender_id"] == "ACC-TEST-B"
    assert alert2_match["receiver_id"] == "ACC-TEST-C"
    assert alert2_match["bridge_entity"] == "ACC-TEST-B"

    # Cleanup
    with SessionLocal() as db:
        db.query(AlertModel).filter(AlertModel.id.in_([alert1_id, alert2_id])).delete(synchronize_session=False)
        db.commit()
