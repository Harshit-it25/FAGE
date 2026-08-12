import requests
import sys
import time
import json

BASE_URL = "http://localhost:8000/api"
# Authenticate and get JWT
try:
    auth_res = requests.post(f"{BASE_URL}/token", data={"username": "admin", "password": "admin123"})
    auth_res.raise_for_status()
    JWT_TOKEN = auth_res.json()["access_token"]
except Exception as e:
    print(f"Failed to authenticate: {e}")
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {JWT_TOKEN}"}

def test_flow():
    start = time.time()
    
    print("1. Authentication / Queue...")
    t0 = time.time()
    res = requests.get(f"{BASE_URL}/alerts?limit=10", headers=HEADERS)
    print(f"   Status: {res.status_code}, Time: {time.time()-t0:.2f}s")

    # ALERT_ID is fetched from the live queue rather than hardcoded: seed_db.py
    # generates a fresh random UUID for every alert on each run, so any ID pinned
    # here previously would silently stop matching the moment the DB was reseeded --
    # producing 404s on every later step of this exact rehearsal without a hard error.
    ALERT_ID = None
    if res.status_code == 200:
        body = res.json()
        items = body.get("alerts", []) if isinstance(body, dict) else body
        if items:
            ALERT_ID = items[0].get("id") or items[0].get("alert_id")
    if not ALERT_ID:
        print("   No seeded alert found -- run seed_db.py first. Aborting rehearsal.")
        sys.exit(1)
    print(f"   Using live alert: {ALERT_ID}")
    
    print("2. Correlate / Open Alert...")
    t0 = time.time()
    res = requests.get(f"{BASE_URL}/correlate/{ALERT_ID}", headers=HEADERS)
    print(f"   Status: {res.status_code}, Time: {time.time()-t0:.2f}s")
    if res.status_code == 200:
        data = res.json()
        print("   Graph nodes:", len(data.get("graph", {}).get("nodes", [])))
    
    print("3. Plain Language Explanation...")
    t0 = time.time()
    res = requests.post(f"{BASE_URL}/alerts/{ALERT_ID}/explain-plain-language", headers=HEADERS)
    print(f"   Status: {res.status_code}, Time: {time.time()-t0:.2f}s")
    
    print("4. Similar Cases...")
    t0 = time.time()
    res = requests.get(f"{BASE_URL}/similar-cases/{ALERT_ID}", headers=HEADERS)
    print(f"   Status: {res.status_code}, Time: {time.time()-t0:.2f}s")
    
    print(f"Total Demo Flow Time: {time.time()-start:.2f}s")

if __name__ == "__main__":
    test_flow()
