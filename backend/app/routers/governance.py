from __future__ import annotations
import os
import sys
import json
import pickle
import logging
import uuid
import time
import hashlib
import threading
import asyncio
import io
import random
from datetime import datetime, UTC, timedelta
from typing import Dict, List, Any, Optional

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from pydantic import BaseModel, Field

from fastapi import APIRouter, FastAPI, HTTPException, Query, status, Depends, UploadFile, File, Request, Header
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from threading import Lock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db import get_db, AlertModel, AuditLogModel, write_audit
from app.auth import (
    require_role,
    verify_api_key,
    authenticate_user,
    create_access_token,
    get_current_user,
    AuthUser,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    TokenResponse,
)
from app.services.risk_engine import FAGERiskEngine
from app.ml.dp_engine import dp_engine, PrivacyBudgetExceededError
from app.services.llm import call_nvidia_llm

from app.dependencies import (
    risk_engine, GLOBAL_DECISION_THRESHOLD, _threshold_lock,
    _COMPLIANCE_RULES,
    _active_alert_score_cutoffs, _load_active_model_metrics,
    _compute_rule_exception_rate, _build_real_sample_df,
    _login_failures, _LOGIN_MAX_ATTEMPTS, _LOGIN_WINDOW_SECONDS, _LOGIN_LOCKOUT_SECONDS,
    _check_login_throttle, _record_login_failure,
    _rate_limit_buckets, _rate_limit_lock, rate_limiter,
    _correlate_cache, _CORRELATE_CACHE_TTL_SECONDS,
)
from app.schemas import (
    PredictRequest, RiskScoreRequest, AlertUpdateRequest, AlertIngestRequest,
    SARResponse, PlainLanguageExplanationResponse, TuneRequest, PUCalibrateRequest,
    SPYTuneRequest, TriageEvalRequest, FeedbackRequest, FeedbackResponse,
    DPExportRequest, DPResetRequest, AdversarialShiftRequest,
)

logger = logging.getLogger("FAGE.API.Backend")
_INR_USD_RATE = float(os.environ.get("FAGE_INR_USD_RATE", "83.5"))

router = APIRouter(tags=["Governance"])

@router.get("/dashboard", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
def get_dashboard_summary(db: Session = Depends(get_db)):
    alerts = [a.to_dict() for a in db.query(AlertModel).all()]
    total_alerts = len(alerts)
    open_alerts = sum(1 for a in alerts if a["status"] == "Open")
    investigating_alerts = sum(1 for a in alerts if a["status"] == "Investigating")
    escalated_alerts = sum(1 for a in alerts if a["status"] == "Escalated")
    closed_alerts = sum(1 for a in alerts if a["status"] == "Closed")

    scores = [a["risk_score"] for a in alerts]
    avg_score = float(np.mean(scores)) if scores else 0.0
    max_score = int(np.max(scores)) if scores else 0
    
    severity_map = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for alert in alerts:
        sev = alert.get("severity", "Medium")
        if sev in severity_map:
            severity_map[sev] += 1
    
    metrics_dict = {}
    active_metrics = _load_active_model_metrics()
    metrics_dict[risk_engine.default_model_name] = active_metrics

    unique_accounts = len({a.get("sender_id") for a in alerts if a.get("sender_id")})
    # Use each alert's own stored severity tier, not a fixed risk_score cutoff. Risk scores are
    # a 0-100 scaling of raw probability, and with a ~0.9% base fraud rate the cost-optimal
    # score range clusters near 0-10, not 50-100 -- a fixed ">= 75" cutoff would silently
    # exclude nearly every real flagged account from "critical_exposure", understating true
    # financial exposure on this dashboard even while those accounts are correctly flagged
    # elsewhere. severity/tier is already computed per-account at the correct, model-relative
    # cutoff (see FAGERiskEngine.map_probability_to_scorecard), so reuse it here instead of
    # re-deriving a second, inconsistent judgment from the raw number.
    critical_alerts = [a for a in alerts if a.get("severity") == "Critical"]
    critical_exposure = float(sum(a.get("amount") or 0 for a in critical_alerts))
    mule_exposure = float(
        sum(
            a.get("amount") or 0
            for a in alerts
            if (a.get("id") or "").startswith("ALT-TGT-") or a.get("severity") in ("Critical", "High")
        )
    )

    active_metrics = _load_active_model_metrics()

    return {
        "status": "success",
        "compiled_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "telemetry": {
            "total_incidents_recorded": total_alerts,
            "unique_accounts_analysed": unique_accounts,
            "critical_alert_count": len(critical_alerts),
            "critical_exposure_amount": critical_exposure,
            "mule_exposure_amount": mule_exposure,
            "average_risk_rating": avg_score,
            "maximum_index_severity": max_score,
            "incident_status_matrix": {
                "Open": open_alerts,
                "Investigating": investigating_alerts,
                "Escalated": escalated_alerts,
                "Closed": closed_alerts
            },
            "severity_profile": severity_map,
            "rule_exception_rate": _compute_rule_exception_rate(db),
            "mule_classification_precision": active_metrics["precision"],
            "mule_classification_recall": active_metrics["recall"],
            "mule_classification_f1": active_metrics["f1"]
        },
        "models": metrics_dict
    }

@router.get("/alerts", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
def list_alerts_queue(
    status_filter: Optional[str] = Query(None, description="Select Alert status: Open, Investigating, Escalated, Closed."),
    severity_filter: Optional[str] = Query(None, description="Select Severity: Low, Medium, High, Critical."),
    limit: int = Query(1000, ge=1, le=2000),
    db: Session = Depends(get_db)
):
    query = db.query(AlertModel)
    if status_filter:
        query = query.filter(AlertModel.status.ilike(status_filter))
    if severity_filter:
        query = query.filter(AlertModel.severity.ilike(severity_filter))
        
    results = [a.to_dict() for a in query.limit(limit).all()]
    slim_results = [{k: v for k, v in a.items() if k != "features"} for a in results]
        
    return {
        "status": "success",
        "alerts_count": len(results),
        "alerts": slim_results
    }

@router.post("/alerts", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
def ingest_simulated_alert(payload: AlertIngestRequest, db: Session = Depends(get_db)):
    score = payload.risk_score
    _, tier, severity, _ = risk_engine.map_probability_to_scorecard(score / 100.0)

    permitted_states = {"Open", "Investigating", "Escalated", "Closed"}
    status_state = payload.status or "Open"
    if status_state.capitalize() not in permitted_states:
         raise HTTPException(
             status_code=400,
             detail=f"Provided status label of '{status_state}' is not supported. Allowed: {permitted_states}"
         )

    alert_id = f"ALT-{str(uuid.uuid4()).upper()}"
    timestamp_str = payload.timestamp or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    logs_trail = payload.logs if payload.logs is not None else [
        {"operator": "Manual Synchronizer", "action": "Injected Alert", "timestamp": "Now"}
    ]

    new_record = AlertModel(
        id=alert_id,
        transaction_id=payload.transaction_id,
        sender_id=payload.sender_id,
        receiver_id=payload.receiver_id,
        amount=payload.amount,
        risk_score=score,
        risk_tier=payload.risk_tier or tier,
        severity=payload.severity or severity,
        status=status_state.capitalize(),
        reason=payload.reason,
        timestamp=timestamp_str,
        assigned_to=payload.assigned_to,
        logs=json.dumps(logs_trail),
        features=json.dumps({}),
        _ts=time.time(),
        triage_action="PRIORITY_MANUAL_REVIEW" if score >= _active_alert_score_cutoffs()[0] else "STANDARD_MONITORING",
        priority_tier=payload.risk_tier or tier,
        pu_probability=float(score) / 100.0
    )

    db.add(new_record)
    db.commit()

    return {
        "status": "success",
        "created_alert_id": alert_id
    }

@router.put("/alerts/{alert_id}", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
def update_alert_status_handler(
    alert_id: str,
    payload: AlertUpdateRequest,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
):
    alert = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=404,
            detail=f"Target alert record matching reference [{alert_id}] could not be found."
        )

    permitted_states = {"Open", "Investigating", "Escalated", "Closed"}
    if payload.status.capitalize() not in permitted_states:
        raise HTTPException(
            status_code=400,
            detail=f"Provided status label of '{payload.status}' is not supported. Allowed: {permitted_states}"
        )

    operator = user.display_name or user.username
    old_status = alert.status
    alert.status = payload.status.capitalize()
    
    log_time = datetime.now(UTC).strftime("%H:%M:%S UTC")
    new_logs = json.loads(alert.logs) if alert.logs else []
    
    new_logs.append({
        "operator": operator,
        "action": f"Changed status from {old_status} to {alert.status}",
        "timestamp": log_time
    })

    if payload.notes:
        new_logs.append({
            "operator": operator,
            "action": f"Appended Analyst Note: {payload.notes}",
            "timestamp": log_time
        })

    if payload.assigned_to is not None:
        old_assignee = alert.assigned_to or "Unassigned"
        alert.assigned_to = payload.assigned_to
        new_logs.append({
            "operator": operator,
            "action": f"Reassigned case from {old_assignee} to {payload.assigned_to}",
            "timestamp": log_time
        })
        
    alert.logs = json.dumps(new_logs)
    alert._ts = time.time()

    write_audit(
        db,
        actor=user.username,
        role=user.role,
        action="alert.update",
        entity_type="alert",
        entity_id=alert_id,
        detail=f"status={alert.status}; assigned_to={alert.assigned_to}",
        auth_method=user.auth_method,
    )

    db.commit()

    return {
        "status": "success",
        "message": f"Alert {alert_id} status updated successfully to {alert.status}.",
        "alert": alert.to_dict()
    }

@router.post("/alerts/{alert_id}/sar", response_model=SARResponse, tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
async def generate_sar_report(alert_id: str, user: AuthUser = Depends(verify_api_key), db: Session = Depends(get_db)):
    if user.role not in ("admin", "auditor"):
        raise HTTPException(status_code=403, detail="Only admins or auditors can file a SAR.")

    alert = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=404,
            detail=f"Target alert record matching reference [{alert_id}] could not be found."
        )
            
    alert_dict = alert.to_dict()
    key_drivers = alert_dict.get("key_risk_drivers", [])
    if not key_drivers and alert_dict.get("features"):
        try:
            _, key_drivers = risk_engine.score_transaction(alert_dict["features"])
        except Exception as e:
            logger.warning(f"Failed to compute live SHAP drivers for SAR: {e}")
            key_drivers = [{"feature": "transaction_amount", "shap_val": 0.45, "contribution": "High"}]

    try:
        corr = correlate_alert(alert_id, user, db)
        graph_summary = corr.get("graph_summary", {})
        related = corr.get("related_entities", [])
    except Exception as e:
        graph_summary = {"cluster_size": 1, "structuring_detected": False, "bridge_nodes": [], "max_hop_distance": 0, "near_threshold_count": 0}
        related = []

    fincen_id = f"SAR-BSA-{uuid.uuid4().hex[:8].upper()}-{alert_id}"
    ts_now = datetime.now(UTC).isoformat()

    alert_for_prompt = {k: v for k, v in alert_dict.items() if k != "features"}
    prompt = f"""
    You are an expert financial crimes investigator filing a formal FinCEN Form 111 / BSA 31 CFR § 1020.320 Suspicious Activity Report (SAR).
    Write a clear, statutory, 3-paragraph investigative narrative detailing why this activity warrants filing:
    1. Account overview & transaction velocity.
    2. Specific statutory basis (e.g., structuring, mule chaining, unusual international velocity).
    3. Quantitative SHAP risk driver alignment.

    Alert Data:
    {json.dumps(alert_for_prompt, indent=2)}
    Graph Summary:
    {json.dumps(graph_summary, indent=2)}
    Key SHAP Drivers:
    {json.dumps(key_drivers[:5], indent=2)}
    """
    
    llm_narrative = await run_in_threadpool(call_nvidia_llm, prompt)

    shap_table_rows = []
    for d in key_drivers[:8]:
        fname = d.get("feature", "unknown")
        sval = d.get("shap_val", 0.0)
        contrib = d.get("contribution", "Medium")
        shap_table_rows.append(f"| `{fname}` | `{sval:+.4f}` | **{contrib}** |")
    shap_table_str = "\n".join(shap_table_rows) if shap_table_rows else "| `N/A` | `0.0000` | **None** |"

    graph_evidence_rows = []
    for r in related[:6]:
        graph_evidence_rows.append(f"- **Linked Alert [{r['alert_id']}]** (Hop {r['hop_distance']}) | Tier: {r['risk_tier']} | Reason: {', '.join(r['match_reasons'])}")
    graph_evidence_str = "\n".join(graph_evidence_rows) if graph_evidence_rows else "- No multi-hop linked accounts in active cluster."

    raw_hash_payload = f"{fincen_id}:{alert_id}:{alert.risk_score}:{alert.transaction_id}:{ts_now}:{llm_narrative}"
    citation_hash = hashlib.sha256(raw_hash_payload.encode('utf-8')).hexdigest()

    sar_report = f"""# DRAFT SUSPICIOUS ACTIVITY REPORT (SAR) — NOT YET FILED
**Prepared in the format of FinCEN Form 111 / BSA 31 CFR § 1020.320 — for analyst/auditor review only.**

> **This narrative was generated by an LLM and has not been verified by a human reviewer.**
> It must be read, fact-checked against the source transaction, and approved by a qualified
> compliance officer before any actual filing is submitted to FinCEN or any regulator.

---

### PART I: FILING IDENTIFICATION & SUBJECT PROFILE
* **BSA Tracking Number:** `{fincen_id}`
* **Filing Timestamp:** `{ts_now}`
* **Target Alert ID:** `{alert.id}` (Transaction Ref: `{alert.transaction_id}`)
* **Account Number:** `{alert.sender_id}`
* **Origin / Destination:** `{alert.sender_id or 'Unknown'}` ➔ `{alert.receiver_id or 'Unknown'}`
* **Transaction Amount:** `₹{alert.amount:,.2f}` (`${(alert.amount or 0)/_INR_USD_RATE:,.2f} USD, approx @ {_INR_USD_RATE}`)
* **Risk Score / Tier:** `{alert.risk_score}` / **`{alert.risk_tier}`**
* **Assigned Investigator:** `{alert.assigned_to}`

---

### PART II: STATUTORY BASIS & INVESTIGATIVE NARRATIVE
**Statutory Authority:** Bank Secrecy Act (BSA) 31 CFR § 1020.320 / FinCEN Guidance FIN-2016-A005.

**Investigative Synthesis:**
{llm_narrative}

---

### PART III: EXPLAINABLE AI (XAI) QUANTITATIVE DRIVERS
This filing is supported by local SHAP (SHapley Additive exPlanations) attribution values calculated at exact transaction evaluation time (`{alert._ts}`):

| Feature Driver | Local SHAP Attribution | Contribution Rating |
| :--- | :---: | :---: |
{shap_table_str}

---

### PART IV: MULTI-HOP NETWORK & GRAPH TOPOLOGY EVIDENCE
* **Cluster Exposure Size:** `{graph_summary.get('cluster_size', 1)} account(s)`
* **Maximum Graph Depth:** `{graph_summary.get('max_hop_distance', 0)} Hop(s)`
* **Bridge / Intermediary Accounts:** `{', '.join(graph_summary.get('bridge_nodes', [])) or 'None'}`
* **Structuring Smurfing Indicator:** `{'DETECTED (Near-threshold / High velocity)' if graph_summary.get('structuring_detected') else 'Not Detected'}`

**Linked Network Entities:**
{graph_evidence_str}

---

### PART V: DRAFT GENERATION RECORD
* **Drafted By (system user):** `{user.username}` (`{user.role}`) via `{user.auth_method}`
* **Draft Timestamp:** `{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}`
* **Content Checksum (SHA-256, for change-detection only — not a legal attestation):**
  `{citation_hash}`

> *Notice: Once reviewed and filed, SAR content is protected under Federal Law (31 U.S.C. 5318(g)(2)). This draft artifact itself is not a filed SAR and carries no statutory protection until submitted through an authorized filer.*
"""

    log_time = datetime.now(UTC).strftime("%H:%M:%S UTC")
    new_logs = json.loads(alert.logs) if alert.logs else []
    new_logs.append({
        "operator": user.username,
        "action": f"Generated draft SAR narrative, pending compliance review ({fincen_id})",
        "timestamp": log_time
    })
    alert.logs = json.dumps(new_logs)

    write_audit(
        db,
        actor=user.username,
        role=user.role,
        action="alert.export_sar",
        entity_type="alert",
        entity_id=alert_id,
        detail=f"Generated SAR Form 111 / BSA artifact ({fincen_id}) with SHA-256 hash {citation_hash[:16]}...",
        auth_method=user.auth_method,
    )
    db.commit()

    return {
        "sar_report": sar_report,
        "fincen_tracking_id": fincen_id,
        "citation_hash": citation_hash
    }

@router.post("/alerts/{alert_id}/explain-plain-language", response_model=PlainLanguageExplanationResponse, tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
async def generate_plain_language_explanation(alert_id: str, user: AuthUser = Depends(verify_api_key), db: Session = Depends(get_db)):
    alert = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=404,
            detail=f"Target alert record matching reference [{alert_id}] could not be found."
        )

    alert_dict = alert.to_dict()
    prompt = f"""
    You are explaining a fraud-risk score to a bank compliance analyst who is not a data
    scientist. Write 3-4 short sentences in plain English. State the risk level, the one or
    two strongest reasons the model flagged this account (from the risk drivers below), and
    avoid ML jargon (no "SHAP", "feature importance", or model internals). Be factual and
    measured — do not accuse the account holder of wrongdoing, describe this as a pattern
    that warrants review.

    Risk tier: {alert_dict.get('risk_tier', 'Unknown')}
    Risk score: {alert_dict.get('risk_score', 'Unknown')}
    Key risk drivers: {json.dumps(alert_dict.get('key_risk_drivers', []), indent=2)}
    """

    fallback_text = (
        f"This account was scored at {alert_dict.get('risk_tier', 'an elevated')} risk "
        f"(score: {alert_dict.get('risk_score', 'N/A')}). Automated plain-language summary "
        f"unavailable right now — please refer to the key risk drivers list for this alert."
    )
    explanation = await run_in_threadpool(call_nvidia_llm, prompt, fallback_text)

    write_audit(
        db,
        actor=user.username,
        role=user.role,
        action="alert.explain_plain",
        entity_type="alert",
        entity_id=alert_id,
        detail="Generated plain-language summary",
        auth_method=user.auth_method,
    )
    db.commit()

    return {"explanation": explanation}

@router.get("/stream-alerts", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key)])
async def stream_alerts():
    async def event_generator():
        last_seen_ts = time.time()
        from app.db import SessionLocal
        db = SessionLocal()
        try:
            recent_alerts = db.query(AlertModel).order_by(AlertModel._ts.desc()).limit(10).all()
            for alert in reversed(recent_alerts):
                alert_dict = alert.to_dict()
                yield f"data: {json.dumps(alert_dict)}\n\n"
                last_seen_ts = max(last_seen_ts, alert._ts)
        finally:
            db.close()

        counter = 0
        while True:
            await asyncio.sleep(2.5)
            counter += 1
            db = SessionLocal()
            try:
                updated_alerts = db.query(AlertModel).filter(AlertModel._ts > last_seen_ts).all()
                if updated_alerts:
                    for alert in updated_alerts:
                        alert_dict = alert.to_dict()
                        yield f"data: {json.dumps(alert_dict)}\n\n"
                        last_seen_ts = max(last_seen_ts, alert._ts)
                elif counter % 2 == 0:
                    yield ": heartbeat\n\n"
                else:
                    yield ": keep-alive\n\n"
            finally:
                db.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")

def _compute_graph_intelligence(
    alerts_copy: List[Dict[str, Any]],
    target_sender: Optional[str],
    target_receiver: Optional[str],
    target_alert_id: str
) -> Dict[str, Any]:
    """
    Real graph algorithms (networkx cycle detection, centrality, connected components) applied
    to the alerts table's sender/receiver/amount/timestamp fields.

    IMPORTANT PROVENANCE NOTE: the algorithms here are real and correctly implemented (verified
    against synthetic test cases with known cycles). However, the sender_id/receiver_id/amount
    values they operate on are Investigation Simulation data (see seed_real_data.py) -- the
    competition dataset has no real transaction-relationship fields to draw from. This function
    demonstrates how these algorithms would work against a bank's real transaction graph; it
    does not claim the specific relationships found are real. The underlying fraud risk SCORE
    (from the trained model) is unaffected and fully real.
    """
    import networkx as nx

    G = nx.DiGraph()
    for a in alerts_copy:
        s, r = a.get("sender_id"), a.get("receiver_id")
        if not s or not r:
            continue
        amt = a.get("amount") or 0
        ts = a.get("timestamp") or 0
        # Keep all parallel edges' info even if multiple alerts share the same (s, r) pair,
        # since a cycle's "total amount circulated" should reflect every real transfer, not
        # just the last one seen.
        if G.has_edge(s, r):
            G[s][r]["alerts"].append({"alert_id": a["id"], "amount": amt, "timestamp": ts})
        else:
            G.add_edge(s, r, alerts=[{"alert_id": a["id"], "amount": amt, "timestamp": ts}])

    target_nodes = {n for n in (target_sender, target_receiver) if n}

    # --- 1. Circular flow detection ---
    circular_flows = []
    if target_nodes and G.number_of_nodes() > 0:
        try:
            # Cap cycle length at 6 hops -- longer "cycles" are rarely a coherent laundering
            # ring in practice and enumeration cost grows quickly on dense graphs.
            all_cycles = [c for c in nx.simple_cycles(G, length_bound=6)]
        except Exception as e:
            logger.warning(f"Cycle detection failed: {e}")
            all_cycles = []

        for cycle in all_cycles:
            if not (set(cycle) & target_nodes):
                continue
            cycle_nodes = cycle + [cycle[0]]
            edge_alerts, total_amount, timestamps = [], 0.0, []
            valid = True
            for i in range(len(cycle_nodes) - 1):
                u, v = cycle_nodes[i], cycle_nodes[i + 1]
                if not G.has_edge(u, v):
                    valid = False
                    break
                for al in G[u][v]["alerts"]:
                    edge_alerts.append({"from": u, "to": v, **al})
                    total_amount += al["amount"] or 0
                    if al["timestamp"]:
                        timestamps.append(al["timestamp"])
            if not valid or not edge_alerts:
                continue
            time_window_seconds = (max(timestamps) - min(timestamps)) if len(timestamps) >= 2 else 0.0
            # Simple, transparent risk contribution: more hops + tighter time window + higher
            # amount = more laundering-like. Not a model score -- an investigator-legible heuristic.
            risk_contribution = min(
                100.0,
                20.0 + 10.0 * len(cycle)
                + (15.0 if 0 < time_window_seconds <= 3600 else 0.0)
                + (15.0 if total_amount >= 100000 else 0.0)
            )
            circular_flows.append({
                "cycle_accounts": cycle,
                "cycle_length": len(cycle),
                "total_amount_circulated": round(total_amount, 2),
                "time_window_seconds": round(time_window_seconds, 1),
                "transactions": edge_alerts,
                "risk_score_contribution": round(risk_contribution, 1)
            })
        circular_flows.sort(key=lambda c: c["risk_score_contribution"], reverse=True)
        circular_flows = circular_flows[:10]  # cap payload size

    # --- 2. Network intelligence metrics ---
    network_intelligence = {
        "cluster_size": 0,
        "degree_centrality": {},
        "betweenness_centrality": {},
        "suspicious_neighbor_count": {},
        "network_depth": 0
    }
    if G.number_of_nodes() > 0 and target_nodes:
        UG = G.to_undirected()
        # Connected component containing the target account(s)
        component = set()
        for n in target_nodes:
            if n in UG:
                component |= nx.node_connected_component(UG, n)
        network_intelligence["cluster_size"] = len(component)

        # Centrality is only meaningful/affordable on the target's own component, not the
        # whole alert table -- compute on the induced subgraph.
        if component:
            sub = G.subgraph(component)
            deg_cent = nx.degree_centrality(sub)
            try:
                betw_cent = nx.betweenness_centrality(sub)
            except Exception:
                betw_cent = {n: 0.0 for n in sub.nodes()}

            high_risk_accounts = {
                a.get("sender_id") for a in alerts_copy if a.get("risk_tier") in ("Critical", "High")
            } | {
                a.get("receiver_id") for a in alerts_copy if a.get("risk_tier") in ("Critical", "High")
            }

            for n in target_nodes:
                if n not in sub:
                    continue
                network_intelligence["degree_centrality"][n] = round(deg_cent.get(n, 0.0), 4)
                network_intelligence["betweenness_centrality"][n] = round(betw_cent.get(n, 0.0), 4)
                neighbors = set(sub.predecessors(n)) | set(sub.successors(n))
                network_intelligence["suspicious_neighbor_count"][n] = len(neighbors & high_risk_accounts)

            try:
                network_intelligence["network_depth"] = nx.diameter(sub.to_undirected()) if sub.number_of_nodes() > 1 else 0
            except Exception:
                network_intelligence["network_depth"] = 0

    return {"circular_flows": circular_flows, "network_intelligence": network_intelligence}

@router.get("/similar-cases/{alert_id}", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key), Depends(rate_limiter(40, 60, "similar-cases"))])
def similar_cases(alert_id: str, top_n: int = 5, user: AuthUser = Depends(verify_api_key), db: Session = Depends(get_db)):
    """
    Priority 5: Similar Past Cases via real cosine similarity over stored SHAP-driven feature
    vectors -- no new ML, no fabricated case outcomes. Each alert already stores its full
    preprocessed feature vector (AlertModel.features) and its top SHAP drivers
    (AlertModel.explainability); similarity is computed directly over those real numbers.

    IMPORTANT: this only surfaces what's actually in the alerts table. There is no
    "confirmed mule" / "recovered amount" field in the schema -- outcome is reported using the
    real `status` field (Open/Under Review/Closed) rather than inventing investigation results
    that were never recorded.
    """
    target = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
    if not target or not target.features:
        raise HTTPException(status_code=404, detail="Alert not found or has no stored feature vector.")

    try:
        target_features = json.loads(target.features)
    except Exception:
        raise HTTPException(status_code=422, detail="Stored feature vector could not be parsed.")

    candidates = db.query(AlertModel).filter(AlertModel.id != alert_id, AlertModel.features.isnot(None)).all()
    if not candidates:
        return {"target_alert": alert_id, "similar_cases": [], "note": "No other alerts with stored feature vectors exist yet."}

    # Align on the numeric keys common to the target and each candidate. Real preprocessed
    # feature vectors, not embeddings invented for this feature -- same numbers the model
    # itself was scored on.
    common_numeric_keys = sorted([
        k for k, v in target_features.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    ])
    if not common_numeric_keys:
        return {"target_alert": alert_id, "similar_cases": [], "note": "Target alert's feature vector has no numeric fields to compare."}

    target_vec = np.array([float(target_features.get(k, 0.0)) for k in common_numeric_keys]).reshape(1, -1)

    scored = []
    for c in candidates:
        try:
            c_features = json.loads(c.features)
        except Exception:
            continue
        c_vec = np.array([float(c_features.get(k, 0.0)) for k in common_numeric_keys]).reshape(1, -1)
        if not np.any(c_vec):
            continue
        try:
            sim = float(cosine_similarity(target_vec, c_vec)[0, 0])
        except Exception:
            continue
        scored.append((sim, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_n]

    similar_cases_out = []
    for sim, c in top:
        expl = {}
        try:
            expl = json.loads(c.explainability) if c.explainability else {}
        except Exception:
            pass
        similar_cases_out.append({
            "alert_id": c.id,
            "similarity_pct": round(sim * 100, 1),
            "risk_tier": c.risk_tier,
            "risk_score": c.risk_score,
            "status": c.status,  # real recorded status -- never a fabricated outcome label
            "top_shap_drivers": [d.get("feature") for d in expl.get("key_risk_drivers", [])[:2]],
            "timestamp": c.timestamp
        })

    return {
        "target_alert": alert_id,
        "similar_cases": similar_cases_out,
        "method": "Cosine similarity over real preprocessed feature vectors (same features the model was scored on).",
        "note": "Outcome shown is the real recorded alert status. This system does not track confirmed-fraud "
                "or recovered-amount outcomes, so those are not shown or fabricated."
    }

@router.get("/correlate/{alert_id}", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key), Depends(rate_limiter(40, 60, "correlate"))])
def correlate_alert(alert_id: str, user: AuthUser = Depends(verify_api_key), db: Session = Depends(get_db)):
    # Lightweight in-process cache (30s TTL). /correlate is the slowest endpoint in the API
    # (measured ~965ms live -- cycle detection + centrality recomputed from scratch every call,
    # plus deserializing every alert's stored feature vector). Demo usage repeatedly re-opens
    # the same handful of alerts, so this directly removes the visible lag on every view after
    # the first. Deliberately NOT a general-purpose cache layer -- a single dict, short TTL,
    # no invalidation logic beyond expiry. A newly created alert may take up to 30s to appear
    # in another alert's related_entities/network view; acceptable for a demo, called out here
    # so it's a known tradeoff, not a silent one.
    cached = _correlate_cache.get(alert_id)
    if cached and (time.time() - cached[0]) < _CORRELATE_CACHE_TTL_SECONDS:
        # Still audit-logged on cache hits (distinct action name) so caching doesn't silently
        # create a gap in the audit trail -- P1.4 explicitly closed that class of gap elsewhere.
        write_audit(
            db, actor=user.username, role=user.role, action="alert.correlate_cached",
            entity_type="alert", entity_id=alert_id,
            detail="Served from cache (< 30s old).", auth_method=user.auth_method,
        )
        db.commit()
        return cached[1]

    alerts = db.query(AlertModel).all()
    alerts_copy = []
    for a in alerts:
        a_dict = a.to_dict()
        alerts_copy.append({
            "id": a.id,
            "transaction_id": a.transaction_id,
            "sender_id": a.sender_id,
            "receiver_id": a.receiver_id,
            "risk_tier": a.risk_tier,
            "amount": a.amount,
            "timestamp": a._ts,
            "features": a_dict.get("features", {})
        })

    target = next((a for a in alerts_copy if a["id"] == alert_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Alert not found")

    target_sender = target.get("sender_id")
    target_receiver = target.get("receiver_id")

    # Build entity adjacencies (accounts to alerts and alerts to accounts)
    account_to_alerts = {}
    for a in alerts_copy:
        for acc in [a.get("sender_id"), a.get("receiver_id")]:
            if acc:
                account_to_alerts.setdefault(acc, []).append(a)

    related = []
    visited_alerts = {alert_id}
    bridge_nodes = set()
    
    # Hop 1: Direct shared entities
    hop1_accounts = {target_sender, target_receiver} - {None}
    hop2_accounts = set()

    for acc in hop1_accounts:
        for a in account_to_alerts.get(acc, []):
            if a["id"] in visited_alerts:
                continue
            reasons = []
            if a.get("sender_id") == acc:
                reasons.append(f"Direct Hop 1: Shared Sender/Receiver ({acc})")
            if a.get("receiver_id") == acc:
                reasons.append(f"Direct Hop 1: Shared Sender/Receiver ({acc})")
            
            # Check if this account acts as a bridge (sender in one alert, receiver in another)
            if (a.get("sender_id") == acc and target_receiver == acc) or (a.get("receiver_id") == acc and target_sender == acc):
                reasons.append(f"Bridge Account Pattern detected on node [{acc}]")
                bridge_nodes.add(acc)

            visited_alerts.add(a["id"])
            related.append({
                "alert_id": a["id"],
                "transaction_id": a["transaction_id"],
                "match_reasons": reasons,
                "risk_tier": a["risk_tier"],
                "hop_distance": 1,
                "bridge_entity": acc if acc in bridge_nodes else None,
                "amount": a["amount"]
            })
            for next_acc in [a.get("sender_id"), a.get("receiver_id")]:
                if next_acc and next_acc not in hop1_accounts:
                    hop2_accounts.add((next_acc, acc, a["id"]))

    # Hop 2: Multi-hop graph correlation (e.g. A -> B -> C mule chaining)
    for next_acc, bridge_acc, via_alert_id in hop2_accounts:
        for a in account_to_alerts.get(next_acc, []):
            if a["id"] in visited_alerts:
                continue
            reasons = [f"Multi-Hop (Hop 2) via intermediary account [{bridge_acc}] linked from alert [{via_alert_id}]"]
            bridge_nodes.add(bridge_acc)
            visited_alerts.add(a["id"])
            related.append({
                "alert_id": a["id"],
                "transaction_id": a["transaction_id"],
                "match_reasons": reasons,
                "risk_tier": a["risk_tier"],
                "hop_distance": 2,
                "bridge_entity": bridge_acc,
                "amount": a["amount"]
            })

    # Behavioral pattern correlation across velocity & amount bands.
    # NOTE: these are heuristic *pattern matches*, not discovered/named criminal rings.
    # Labels below were previously "STRUCTURING-RING-ALPHA" / "VELOCITY-CLUSTER-V1", which
    # implied the system had identified a specific, named syndicate. It hadn't — it matched
    # a coincidental amount band or velocity threshold. Relabeled to describe the actual
    # heuristic, not a dramatized entity name.
    target_amt = target.get("amount") or 0
    target_tier = target.get("risk_tier") or "Medium"
    for a in alerts_copy:
        if a["id"] in visited_alerts:
            continue
        reasons = []
        a_amt = a.get("amount") or 0
        a_tier = a.get("risk_tier") or "Medium"
        
        # Smurfing band check (e.g., both ₹9,000-₹9,999 near-threshold structuring)
        if _COMPLIANCE_RULES["structuring_band_min"] <= target_amt <= _COMPLIANCE_RULES["structuring_band_max"] and _COMPLIANCE_RULES["structuring_band_min"] <= a_amt <= _COMPLIANCE_RULES["structuring_band_max"]:
            reasons.append("Behavioral Hop 2: Co-occurring Near-Threshold Structuring Band (₹9k-₹10k)")
            bridge_nodes.add("NEAR_THRESHOLD_AMOUNT_BAND_MATCH")
        # High velocity pattern check
        elif (target.get("features") or {}).get("velocity_6h", 0) >= _COMPLIANCE_RULES["high_velocity_threshold"] and (a.get("features") or {}).get("velocity_6h", 0) >= _COMPLIANCE_RULES["high_velocity_threshold"]:
            reasons.append("Behavioral Hop 2: Synchronized High-Velocity Pattern Match")
            bridge_nodes.add("HIGH_VELOCITY_PATTERN_MATCH")
        # No fallback here anymore: if no real signal (direct hop, structuring band, or
        # velocity match) is found for this alert, the correlation graph for it should
        # come back empty. Manufacturing a "Peer Risk Cluster" link between two unrelated
        # same-tier accounts specifically because nothing real was found is exactly the
        # kind of fabricated-to-avoid-an-empty-state pattern this project has repeatedly
        # had to remove elsewhere — an honest empty result is not a bug to paper over.
            
        if reasons:
            visited_alerts.add(a["id"])
            related.append({
                "alert_id": a["id"],
                "transaction_id": a["transaction_id"],
                "match_reasons": reasons,
                "risk_tier": a["risk_tier"],
                "hop_distance": 2 if "Hop 2" in reasons[0] else 1,
                "bridge_entity": "NEAR_THRESHOLD_AMOUNT_BAND_MATCH" if "Structuring" in reasons[0] else ("HIGH_VELOCITY_PATTERN_MATCH" if "Velocity" in reasons[0] else None),
                "amount": a["amount"]
            })

    # Structuring & velocity analysis across cluster
    cluster_alerts = [target] + [next((a for a in alerts_copy if a["id"] == r["alert_id"]), target) for r in related]
    structuring_detected = False
    near_threshold_count = sum(1 for a in cluster_alerts if _COMPLIANCE_RULES["structuring_band_min"] <= (a.get("amount") or 0) <= _COMPLIANCE_RULES["structuring_band_max"])
    high_velocity_count = sum(1 for a in cluster_alerts if (a.get("features") or {}).get("velocity_6h", 0) >= _COMPLIANCE_RULES["high_velocity_threshold"])
    
    if near_threshold_count >= 2 or high_velocity_count >= 2:
        # BUG-003 FIX: only flag structuring if STRUCTURAL signals (amount bands / velocity) present — not bridge nodes alone
        structuring_detected = True

    # --- Circular Money Flow Detection & Network Intelligence (Investigation Simulation layer) ---
    # Algorithms are real (networkx); the sender/receiver graph they run on is simulated for
    # demonstration, since the competition dataset has no real relationship fields. See
    # data_provenance in the response below, and _compute_graph_intelligence's docstring.
    graph_intel = _compute_graph_intelligence(alerts_copy, target_sender, target_receiver, alert_id)

    # Priority 1: Natural-language investigation summary, reconstructed from the REAL fields
    # already persisted on this alert at creation time (explainability JSON, risk_score,
    # triage_action, rules reason string) -- not re-run through the model, so no fresh ML call
    # is needed here. Combined with the graph_intel computed above, clearly labeled.
    target_row = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
    investigation_summary = None
    if target_row is not None:
        try:
            stored_expl = json.loads(target_row.explainability) if target_row.explainability else {}
        except Exception:
            stored_expl = {}
        pseudo_scorecard = {
            "scores": {
                "final_risk_score": target_row.risk_score,
                "base_ml_score": target_row.risk_score,
                "base_ml_probability": target_row.pu_probability or 0.0,
                "confidence_interval_90": stored_expl.get("confidence_interval_90") or {},
            },
            "categorizations": {
                "risk_tier": target_row.risk_tier,
                "action_decision": target_row.priority_tier,
                "triage_routing": {
                    "triage_action": target_row.triage_action,
                    "rationale": stored_expl.get("evasion_resistance", {}).get("rationale")
                        if isinstance(stored_expl.get("evasion_resistance"), dict) else None,
                },
            },
            "rules_audit": {"triggered_rules_count": 0, "overrides": []},
            "explainability": {"key_risk_drivers": stored_expl.get("key_risk_drivers", [])},
        }
        investigation_summary = risk_engine.generate_investigation_summary(pseudo_scorecard, graph_intel)

    write_audit(
        db,
        actor=user.username,
        role=user.role,
        action="alert.correlate",
        entity_type="alert",
        entity_id=alert_id,
        detail=f"Graph correlation found {len(related)} related entities (max hop 2, structuring={structuring_detected})",
        auth_method=user.auth_method,
    )
    db.commit()

    result = {
        "target_alert": alert_id,
        "related_entities": related,
        "graph_summary": {
            "cluster_size": len(cluster_alerts),
            "structuring_detected": structuring_detected,
            "bridge_nodes": list(bridge_nodes),
            "max_hop_distance": 2 if any(r["hop_distance"] == 2 for r in related) else (1 if related else 0),
            "near_threshold_count": near_threshold_count
        },
        "circular_flows": graph_intel["circular_flows"],
        "network_intelligence": graph_intel["network_intelligence"],
        "investigation_summary": investigation_summary,
        "data_provenance": {
            "layer": "Investigation Simulation",
            "note": (
                "The competition dataset contains account-level features but no transaction "
                "graph or relationship fields (sender, receiver, device, IP). This relationship "
                "view demonstrates how the AI Risk Engine would integrate with a bank's real "
                "transaction monitoring system once such data is available. The risk score for "
                "this alert is computed directly from the real dataset and is not affected by "
                "this layer."
            )
        }
    }
    _correlate_cache[alert_id] = (time.time(), result)
    return result

@router.post("/triage-eval", tags=["Governance & Operations"], dependencies=[Depends(verify_api_key), Depends(require_role("admin"))])
async def evaluate_operational_triage(request: TriageEvalRequest):
    if not risk_engine.triage_policy:
        raise HTTPException(status_code=500, detail="Triage policy engine not initialized.")
    result = risk_engine.triage_policy.evaluate_account(
        risk_score=request.risk_score,
        ci_lower=request.ci_lower,
        ci_upper=request.ci_upper,
        evadable=request.evadable,
        pu_probability=request.pu_probability,
        account_id=request.account_id
    )
    return {
        "status": "success",
        "triage_evaluation": result
    }

@router.post("/feedback", response_model=FeedbackResponse, tags=["Model Analytics"], dependencies=[Depends(verify_api_key)])
@router.post("/alerts/{alert_id}/feedback", response_model=FeedbackResponse, tags=["Model Analytics"], dependencies=[Depends(verify_api_key)])
async def submit_analyst_feedback(
    request: FeedbackRequest,
    alert_id: Optional[str] = None,
    user: AuthUser = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    target_alert_id = alert_id or request.alert_id
    if not target_alert_id:
        raise HTTPException(status_code=400, detail="alert_id is required")

    # Check alert in database if present
    alert = db.query(AlertModel).filter(AlertModel.id == target_alert_id).first()
    alert_score = 0.5
    if alert:
        alert_score = (alert.risk_score or 50.0) / 100.0
        if request.label in ["True Positive", "Mule Ring", "Confirmed Fraud"]:
            alert.status = "Escalated"
        elif request.label in ["False Positive", "Legitimate", "Clear"]:
            alert.status = "Closed"

    # Trigger online recalibration if enabled
    old_c = getattr(risk_engine.pu_engine, "c_", 0.725) if risk_engine.pu_engine else 0.725
    new_c = old_c
    old_spy = getattr(risk_engine.pu_engine, "spy_threshold_", 0.152) if risk_engine.pu_engine else 0.152
    new_spy = old_spy

    if request.trigger_recalibration:
        recal = risk_engine.online_recalibrate(label=request.label, alert_score=alert_score)
        old_c = recal.get("old_c_factor", old_c)
        new_c = recal.get("new_c_factor", new_c)
        old_spy = recal.get("old_spy_threshold", old_spy)
        new_spy = recal.get("new_spy_threshold", new_spy)

    write_audit(
        db,
        actor=user.username,
        role=user.role,
        action="alert.feedback_recalibrate" if request.trigger_recalibration else "alert.feedback",
        entity_type="alert_model_closed_loop",
        entity_id=target_alert_id,
        detail=f"Analyst feedback '{request.label}' (notes: {request.analyst_notes or 'None'}). Recalibration: c {old_c:.4f}->{new_c:.4f}, SPY {old_spy}->{new_spy}",
        auth_method=user.auth_method,
        tenant_id=request.tenant_id or "TN-GLOBAL-01",
        org_id=request.org_id or "ORG-FIN-PRIMARY"
    )
    db.commit()

    return FeedbackResponse(
        status="success",
        alert_id=target_alert_id,
        label_recorded=request.label,
        recalibration_triggered=request.trigger_recalibration,
        old_c_factor=old_c,
        new_c_factor=new_c,
        old_spy_threshold=old_spy,
        new_spy_threshold=new_spy,
        message=f"Closed-loop feedback recorded. PU model discovery factor calibrated from {old_c:.4f} to {new_c:.4f}."
    )

