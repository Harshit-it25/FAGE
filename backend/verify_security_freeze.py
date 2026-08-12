import os
import requests
import json
import time

BASE_URL = "http://localhost:8000/api"

print("=========================================")
print("AUTHENTICATION BOUNDARY TEST")
print("=========================================")

def test_auth(desc, headers):
    try:
        res = requests.get(f"{BASE_URL}/alerts", headers=headers)
        print(f"{desc:<30} -> {res.status_code}")
        return res.status_code
    except Exception as e:
        print(f"{desc:<30} -> Connection Error")
        return None

# 1. No credentials
test_auth("No credentials", {})

# 2. Invalid API key
test_auth("Invalid API key", {"x-api-key": "invalid-key"})

# 3. Old demo key
test_auth("Old demo key", {"x-api-key": "[ROTATED_DEMO_KEY]"})

# Get valid JWT
try:
    auth_res = requests.post(f"{BASE_URL}/token", data={"username": "admin", "password": "admin123"})
    JWT_TOKEN = auth_res.json()["access_token"]
    test_auth("Valid JWT", {"Authorization": f"Bearer {JWT_TOKEN}"})
except Exception as e:
    print("Failed to get valid JWT")

# 5. Tampered JWT
if 'JWT_TOKEN' in locals():
    tampered = JWT_TOKEN[:-5] + "12345"
    test_auth("Tampered JWT", {"Authorization": f"Bearer {tampered}"})

print("=========================================")
print("PRODUCTION JWT SECRET HOSTILE TEST")
print("=========================================")

print("This must be tested manually or by booting servers via subprocess.")

import subprocess

def boot_and_test(env_vars, case_name):
    print(f"\nTesting: {case_name}")
    env = os.environ.copy()
    env.update(env_vars)
    # Ensure to use the venv python
    python_exe = os.path.join("venv", "Scripts", "python.exe")
    
    # Start server in background
    process = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "app.main:app", "--port", "8080"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # Wait a bit to see if it starts
    time.sleep(3)
    if process.poll() is not None:
        print("Result: APPLICATION FAILS TO START")
        # Print output to confirm reason
        stdout, _ = process.communicate()
        for line in stdout.split('\n'):
            if "CRITICAL SECURITY ERROR" in line:
                print(f"Reason: {line.strip()}")
                break
    else:
        print("Result: APPLICATION STARTS")
        process.terminate()
        process.wait()

boot_and_test({"FAGE_ENV": "production", "FAGE_JWT_SECRET": ""}, "Case 1: FAGE_ENV=production, FAGE_JWT_SECRET missing")
boot_and_test({"FAGE_ENV": "production", "FAGE_JWT_SECRET": "fage-dev-jwt-secret-change-in-production"}, "Case 2: FAGE_ENV=production, FAGE_JWT_SECRET=development secret")
boot_and_test({"FAGE_ENV": "production", "FAGE_JWT_SECRET": "secure-random-secret-123"}, "Case 3: FAGE_ENV=production, FAGE_JWT_SECRET=secure random")
boot_and_test({"FAGE_ENV": "test", "FAGE_JWT_SECRET": "fage-dev-jwt-secret-change-in-production"}, "Case 4: FAGE_ENV=test, development secret")

