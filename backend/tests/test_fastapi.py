import sys
import os
import traceback

sys.path.insert(0, os.path.abspath('.'))
os.environ['FAGE_ENV'] = 'test'
os.environ['FAGE_JWT_SECRET'] = 'test-secret-123'

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, base_url="http://testserver/api")

print("\n--- Testing /health ---")
try:
    res = client.get("/health")
    print(res.status_code)
    print(res.text)
except Exception as e:
    traceback.print_exc()

print("\n--- Testing /token ---")
try:
    res = client.post("/token", data={"username": "admin", "password": "admin123"})
    print(res.status_code)
    print(res.text)
except Exception as e:
    traceback.print_exc()

