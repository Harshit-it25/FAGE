import os
import asyncio
import sys

sys.stdout.reconfigure(encoding='utf-8')

import pytest
if "NVIDIA_API_KEY" not in os.environ:
    pytest.skip("NVIDIA_API_KEY not found in environment. Skipping LLM tests.", allow_module_level=True)
# Use test db
os.environ["DATABASE_URL"] = "sqlite:///./fage_alerts_test.db"
os.environ["FAGE_JWT_SECRET"] = "fage-dev-jwt-secret-change-in-production"
os.environ["ENVIRONMENT"] = "development"

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_sar_endpoint():
    print("Testing SAR generation endpoint...")
    res = client.post("/token", data={"username": "admin", "password": "admin123"})
    jwt_token = res.json()["access_token"]
    response = client.post(
        "/alerts/ALT-2024-9182/sar",
        headers={"Authorization": f"Bearer {jwt_token}"}
    )
    if response.status_code == 200:
        data = response.json()
        print("SUCCESS! SAR report generated:")
        
        with open("sar_output.md", "w", encoding="utf-8") as f:
            f.write(data["sar_report"])
        print("Saved to sar_output.md")
    else:
        print(f"FAILED: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    test_sar_endpoint()
