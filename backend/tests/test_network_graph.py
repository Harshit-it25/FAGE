import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, engine, get_db
from sqlalchemy.orm import sessionmaker
from app.db import AlertModel

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)
VALID_API_KEY = "sk_test_demo_key_9384729"

@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Create test alerts
    alert1 = AlertModel(
        id="TEST-ALERT-1",
        transaction_id="TXN-1",
        sender_id="ACC-A",
        receiver_id="ACC-B",
        amount=10000,
        risk_score=75,
        priority_tier="High",
        status="Open",
        features='{}',
        explainability='{}'
    )
    alert2 = AlertModel(
        id="TEST-ALERT-2",
        transaction_id="TXN-2",
        sender_id="ACC-B",
        receiver_id="ACC-C",
        amount=5000,
        risk_score=85,
        priority_tier="Critical",
        status="Open",
        features='{}',
        explainability='{}'
    )
    db.add(alert1)
    db.add(alert2)
    db.commit()
    yield
    db.query(AlertModel).delete()
    db.commit()
    Base.metadata.drop_all(bind=engine)

def test_correlate_alert_returns_sender_and_receiver():
    response = client.get(
        "/api/v1/governance/correlate/TEST-ALERT-1",
        headers={"Authorization": f"Bearer {VALID_API_KEY}"}
    )
    assert response.status_code == 200
    data = response.json()
    
    # Check target
    assert data["target_alert"] == "TEST-ALERT-1"
    assert data["target_sender"] == "ACC-A"
    assert data["target_receiver"] == "ACC-B"
    
    # Check related entities
    related = data["related_entities"]
    assert len(related) > 0
    # Find TEST-ALERT-2 in related
    alert2 = next(a for a in related if a["alert_id"] == "TEST-ALERT-2")
    assert alert2["sender_id"] == "ACC-B"
    assert alert2["receiver_id"] == "ACC-C"
    
    # Check that bridge entity is ACC-B (since it's Hop 1 shared entity)
    assert alert2["bridge_entity"] == "ACC-B"
