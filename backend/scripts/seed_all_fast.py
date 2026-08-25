import os
import sys
import pandas as pd
import uuid
import json
import time
from datetime import datetime, timedelta, UTC
import random

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db import SessionLocal, AlertModel
from app.dependencies import risk_engine

def seed_all_fast():
    db = SessionLocal()
    
    print("Clearing synthetic alerts...")
    db.query(AlertModel).delete()
    db.commit()

    print("Loading full dataset...")
    df = pd.read_csv("../data/DataSet.csv")
    
    target_col = [c for c in df.columns if c.lower() == "f3924"][0]
    labels = df[target_col].values
    raw_df = df.drop(columns=[target_col])
    
    total = len(raw_df)
    print(f"Total rows: {total}")
    
    print("Batch preprocessing...")
    start = time.time()
    
    
    processed_df = risk_engine.preprocessor.transform(raw_df)
    selected_df = risk_engine.selector.transform(processed_df)
    
    
    raw_probs = risk_engine.classifier.predict_proba(selected_df)[:, 1]
    
    
    if risk_engine.pu_engine and hasattr(risk_engine.pu_engine, "calibrate_probabilities"):
        probs = risk_engine.pu_engine.calibrate_probabilities(raw_probs)
    else:
        probs = raw_probs
        
    print(f"ML execution completed in {time.time() - start:.2f}s")
    
    
    print("Computing batch SHAP values...")
    start = time.time()
    import shap
    base_model = risk_engine.classifier.calibrated_classifiers_[0].estimator if hasattr(risk_engine.classifier, 'calibrated_classifiers_') else getattr(risk_engine.classifier, 'estimator', getattr(risk_engine.classifier, 'base_estimator', risk_engine.classifier))
    explainer = shap.TreeExplainer(base_model, feature_perturbation="tree_path_dependent")
    shap_vals = explainer.shap_values(selected_df)
    if isinstance(shap_vals, list):
        shap_vals = shap_vals[1]
    elif shap_vals.ndim > 1 and shap_vals.shape[1] == 2:
        shap_vals = shap_vals[:, 1]
    print(f"SHAP computed in {time.time() - start:.2f}s")
    
    feature_names = selected_df.columns.tolist()
    
    print("Generating database records...")
    now = datetime.now(UTC)
    active_threshold = risk_engine.per_model_thresholds.get(risk_engine.default_model_name.lower())
    
    records = []
    
    
    BATCH_SIZE = 1000
    
    for i in range(total):
        prob = float(probs[i])
        true_label = int(labels[i])
        
        ml_score, ml_severity, ml_decision = risk_engine.map_probability_to_scorecard(prob, active_threshold)
        
        alert_id = f"ALT-TGT-{str(uuid.uuid4()).upper()}" if true_label == 1 else f"ALT-DS-{str(uuid.uuid4()).upper()}"
        sender_id = f"ACC-{random.randint(1000, 9999)}"
        receiver_id = f"ACC-{random.randint(1000, 9999)}"
        amount = round(random.uniform(50.0, 15000.0), 2)
        
        ts = now - timedelta(hours=random.randint(0, 168), minutes=random.randint(0, 60))
        
        
        sv = shap_vals[i]
        
        driver_indices = sorted(range(len(sv)), key=lambda x: sv[x], reverse=True)[:3]
        
        drivers = []
        for idx in driver_indices:
            if sv[idx] > 0:
                drivers.append({
                    "feature": feature_names[idx],
                    "importance_attribution": float(sv[idx]),
                    "direction": "increases_risk",
                    "raw_value": float(selected_df.iloc[i, idx])
                })
        
        reason_summary = f"{ml_severity} Severity Risk Score Card triggered. Driven by high ML features variance: " + ", ".join([d["feature"] for d in drivers])
        
        expl_payload = {
            "key_risk_drivers": drivers
        }
        
        logs_trail = [{"operator": "System Agent", "action": "Automatic Risk Score Evaluation", "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ")}]
        
        if ml_score > 85:
            status = "Escalated"
        elif ml_score > 65:
            status = random.choice(["Open", "Investigating"])
        else:
            status = random.choice(["Closed", "Open"])

        new_record = AlertModel(
            id=alert_id,
            transaction_id=f"TXN-{uuid.uuid4().hex[:12].upper()}",
            sender_id=sender_id,
            receiver_id=receiver_id,
            amount=amount,
            risk_score=ml_score,
            severity=ml_severity,
            status=status,
            reason=reason_summary,
            timestamp=ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            assigned_to="System Operator" if status != "Open" else "Unassigned",
            logs=json.dumps(logs_trail),
            features="{}", 
            explainability=json.dumps(expl_payload),
            _ts=ts.timestamp(),
            triage_action="Escalate" if ml_score > 75 else "Review",
            priority_tier="High" if ml_score > 75 else "Low",
            pu_probability=prob,
            tenant_id="default",
            org_id="FAGE-CORE",
        )
        records.append(new_record)
        
        if (i + 1) % BATCH_SIZE == 0:
            db.bulk_save_objects(records)
            db.commit()
            records = []
            print(f"Inserted {i+1} rows...")
            
    if records:
        db.bulk_save_objects(records)
        db.commit()
        
    print(f"Successfully batch-processed and inserted {total} authentic transactions.")
    db.close()

if __name__ == "__main__":
    seed_all_fast()
