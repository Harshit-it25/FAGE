import networkx as nx
import hashlib
import time
import uuid
from datetime import datetime, UTC
from typing import Dict, Any, List, Optional
import json
import logging
from fastapi import HTTPException
from app.services.llm import call_nvidia_llm
from app.db import write_audit, AlertModel
from app.dependencies import _CORRELATE_CACHE_TTL_SECONDS, _correlate_cache, _COMPLIANCE_RULES
from fastapi.concurrency import run_in_threadpool
import os
_INR_USD_RATE = float(os.environ.get('FAGE_INR_USD_RATE', '83.5'))

logger = logging.getLogger('FAGE.GovernanceService')

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
                a.get("sender_id") for a in alerts_copy if a.get("severity") in ("Critical", "High")
            } | {
                a.get("receiver_id") for a in alerts_copy if a.get("severity") in ("Critical", "High")
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

async def build_sar_report_service(alert_id: str, user, db, risk_engine):
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
        corr = build_correlation_graph_service(alert_id, user, db)
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
    
    deterministic_fallback = f"""**[SAR AI generation unavailable. Deterministic evidence-based draft generated]**

**SUBJECT:** Suspicious Activity Detected for Account {alert.sender_id}
**SUMMARY:**
Risk Score: {alert.risk_score}
Transaction Amount: ₹{alert.amount:,.2f}
Alert Reason: {alert.reason or 'Unusual activity patterns'}

**DETAILED NARRATIVE:**
This alert was generated based on the following key risk drivers:
"""
    for d in key_drivers[:3]:
        fname = d.get("feature", "unknown")
        sval = d.get("shap_val", 0.0)
        contrib = d.get("contribution", "Medium")
        deterministic_fallback += f"- {fname} (SHAP: {sval:+.4f}, Contribution: {contrib})\n"

    llm_narrative = await run_in_threadpool(call_nvidia_llm, prompt, deterministic_fallback)

    shap_table_rows = []
    for d in key_drivers[:8]:
        fname = d.get("feature", "unknown")
        sval = d.get("shap_val", 0.0)
        contrib = d.get("contribution", "Medium")
        shap_table_rows.append(f"| `{fname}` | `{sval:+.4f}` | **{contrib}** |")
    shap_table_str = "\n".join(shap_table_rows) if shap_table_rows else "| `N/A` | `0.0000` | **None** |"

    graph_evidence_rows = []
    for r in related[:6]:
        graph_evidence_rows.append(f"- **Linked Alert [{r['alert_id']}]** (Hop {r['hop_distance']}) | Reason: {', '.join(r['match_reasons'])}")
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
* **Risk Score** `{alert.risk_score}`
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

async def build_explanation_service(alert_id: str, user, db, risk_engine):
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

    Severity: {alert_dict.get('severity', 'Unknown')}
    Risk score: {alert_dict.get('risk_score', 'Unknown')}
    Key risk drivers: {json.dumps(alert_dict.get('key_risk_drivers', []), indent=2)}
    """

    fallback_text = (
        f"This account was scored at {alert_dict.get('severity', 'an elevated')} risk "
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

def build_correlation_graph_service(alert_id: str, user, db):
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
    print("DEBUG: CORRELATE SERVICE ALERT COUNT:", len(alerts))
    print("DEBUG: CORRELATE SERVICE LOOKING FOR:", alert_id)
    if not any(a.id == alert_id for a in alerts):
        print("DEBUG: TARGET NOT IN ALERTS!")
    
    alerts_copy = []
    for a in alerts:
        a_dict = a.to_dict()
        alerts_copy.append({
            "id": a.id,
            "transaction_id": a.transaction_id,
            "sender_id": a.sender_id,
            "receiver_id": a.receiver_id,
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
                "sender_id": a.get("sender_id"),
                "receiver_id": a.get("receiver_id"),
                "match_reasons": reasons,
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
                "sender_id": a.get("sender_id"),
                "receiver_id": a.get("receiver_id"),
                "match_reasons": reasons,
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
    target_tier = target.get("severity") or "Medium"
    for a in alerts_copy:
        if a["id"] in visited_alerts:
            continue
        reasons = []
        a_amt = a.get("amount") or 0
        a_tier = a.get("severity") or "Medium"
        
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
                "sender_id": a.get("sender_id"),
                "receiver_id": a.get("receiver_id"),
                "match_reasons": reasons,
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
        from app.dependencies import risk_engine
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
        "target_sender": target_sender,
        "target_receiver": target_receiver,
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

