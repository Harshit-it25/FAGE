import json
import os
import pandas as pd
import numpy as np

# Load target alerts
dir_path = os.path.dirname(os.path.abspath(__file__))
target_alerts_path = os.path.join(dir_path, "target_alerts.json")
csv_path = os.path.join(os.path.dirname(os.path.dirname(dir_path)), "fage_final_risk_scores.csv")

with open(target_alerts_path, "r") as f:
    alerts = json.load(f)

# Filter out existing low-risk and dataset alerts to ensure idempotency and clean regenerate
alerts = [a for a in alerts if not (a["id"].startswith("ALT-LOW-") or a["id"].startswith("ALT-DS-"))]

print(f"Original target alerts count: {len(alerts)}")

# Load CSV risk scores
df = pd.read_csv(csv_path)

# Sample 681 rows from the entire dataset (representing 25% of the dataset)
np.random.seed(42)
sampled_df = df.sample(681)

# Use features template from ALT-TGT-001
template_alert = alerts[0]
template_features = template_alert["features"]
low_features = {k: 0.0 for k in template_features.keys()}

# Generate 681 dataset alerts
new_alerts = []
for idx, (row_idx, row) in enumerate(sampled_df.iterrows()):
    alert_id = f"ALT-DS-{idx+1:03d}"
    txn_id = f"TXN_DS_{row_idx+1000}"
    sender_id = f"ACC-DS-{idx+1:03d}"
    receiver_id = f"ACC-REC-{idx+1:03d}"
    amount = float(np.random.randint(150, 1800))
    score = int(np.round(row["Final_Risk_Score"]))
    
    # Ensure score is at least 2 to show some low risk rating
    score = max(score, 2)
    
    # Map tier, severity, and reason dynamically based on score
    if score >= 75:
        tier = "Critical"
        severity = "Critical"
        reason = f"Dataset Target Fraud Account (Row {row_idx}, Label F3924 = 1). ML probability: {row['ML_Risk']:.4f}."
    elif score >= 50:
        tier = "High"
        severity = "High"
        reason = f"Dataset Target Fraud Account (Row {row_idx}, Label F3924 = 1). ML probability: {row['ML_Risk']:.4f}."
    elif score >= 25:
        tier = "Medium"
        severity = "Medium"
        reason = f"Dataset Medium Risk Account (Row {row_idx}). Moderate risk characteristics. ML score: {row['ML_Risk']:.4f}."
    else:
        tier = "Low"
        severity = "Low"
        reason = f"Low Risk Dataset Account (Row {row_idx}). Verified low-risk behavioral characteristics. ML score: {row['ML_Risk']:.4f}."
    
    # Status distribution: 50% Open, 50% Closed
    status = "Open" if idx % 2 == 0 else "Closed"
    
    new_alert = {
        "id": alert_id,
        "transaction_id": txn_id,
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "amount": amount,
        "risk_score": score,
        "risk_tier": tier,
        "severity": severity,
        "status": status,
        "reason": reason,
        "timestamp": "2026-05-30T14:00:00Z",
        "assigned_to": "Unassigned",
        "logs": [
            {
                "operator": "System Agent",
                "action": "Automatic Risk Score Evaluation",
                "timestamp": "14:00:00 UTC"
            }
        ],
        "features": low_features
    }
    
    # If closed, add closed log
    if status == "Closed":
        new_alert["assigned_to"] = "Admin (Operator)"
        new_alert["logs"].append({
            "operator": "Admin (Operator)",
            "action": "Changed status from Open to Closed",
            "timestamp": "15:00:00 UTC"
        })
        new_alert["logs"].append({
            "operator": "Admin (Operator)",
            "action": "Appended Analyst Note: System auto-resolve. Confirmed normal customer transfers.",
            "timestamp": "15:00:00 UTC"
        })
        
    new_alerts.append(new_alert)

# Append to original alerts list (we can mix them or put them at the end. Let's put them in order of ID)
# Let's insert them so that we have a mixed view. E.g., we can append them at the end.
combined_alerts = alerts + new_alerts

with open(target_alerts_path, "w") as f:
    json.dump(combined_alerts, f, indent=4)

print(f"Saved {len(combined_alerts)} alerts to target_alerts.json")
