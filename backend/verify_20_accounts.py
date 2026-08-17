import os
import sys
import pandas as pd
import json

from app.db import SessionLocal, AlertModel

def verify_20_accounts():
    db = SessionLocal()
    alerts = db.query(AlertModel).limit(20).all()
    
    print("-" * 100)
    print(f"{'Account ID':<15} | {'Risk Score':<10} | {'Probability':<12} | {'Confidence(%)':<14} | {'Severity':<10} | {'Triage':<20}")
    print("-" * 100)
    
    for a in alerts:
        p = a.pu_probability
        conf_display = "N/A"
        
        print(f"{a.account_id if hasattr(a, 'account_id') else a.sender_id:<15} | {a.risk_score:<10.1f} | {p:<12.4f} | {conf_display:<14} | {a.severity:<10} | {a.triage_action:<20}")

if __name__ == "__main__":
    verify_20_accounts()
