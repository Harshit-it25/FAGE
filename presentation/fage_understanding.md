# FAGE (Fraud Assessment & Governance Engine)
**Project Understanding & Operational Overview**

> **Objective:** A comprehensive, high-level breakdown of exactly what FAGE does, the business problem it solves, how analysts use it, and the fundamental concepts driving the AI.

---

## 1. The Core Business Problem FAGE Solves

Modern financial institutions, payment gateways, and fintechs are losing billions of Rupees. But they aren't just losing money to obvious scams; they are losing money to **Hidden Fraud** and operational **Alert Fatigue**.

1. **The Hidden Fraud Problem:** Traditional ML anti-fraud models are built using standard supervised learning. They are trained on what analysts caught in the past (Positives) and assume everything else is clean (Negatives). This is fundamentally flawed. Smart money mule rings and sophisticated launderers intentionally stay under the radar. By treating unflagged data as "clean," traditional AI actively learns to ignore the smartest criminals.
2. **Alert Fatigue:** Old rule-based engines generate 10,000 alerts a day. A human analyst team can realistically only review 500. Sending thousands of low-impact, false-positive alerts causes operational paralysis. 

**FAGE** completely dismantles this by mathematically discovering hidden fraud and economically calculating whether an alert is actually worth investigating.

---

## 2. The Solution: How FAGE Works (The Pipeline)

When a transaction (e.g., a transfer of ₹50,000) occurs, FAGE processes it through a highly optimized 6-stage pipeline:

1. **Ingestion & Guarding:** The system receives the raw transaction payload. It immediately runs strict data validation to prevent adversarial tampering.
2. **Behavioral Coercion:** FAGE transforms raw data into behavioral math (e.g., how fast are they moving money? Does their IP location match their banking jurisdiction?).
3. **PU-Calibrated Scoring:** The Machine Learning model outputs a raw risk score. But critically, the **Positive-Unlabeled (PU) Engine** kicks in. It adjusts the probability by asking: *"Does this look like the stealthy fraud we normally miss?"* 
4. **Economic Triage:** FAGE evaluates the cost. If the fraud is for ₹500, but a manual review costs ₹2,000 in labor overhead, the Triage Policy suppresses the alert. If it detects "Micro-Structuring" (e.g., transferring ₹49,999 to dodge a ₹50,000 regulatory trigger), it instantly fast-tracks the alert regardless of amount.
5. **Graph Correlation (Mule Hunting):** FAGE scans the database up to 2 hops away. If this transaction is connected to a known scammer through an intermediary "Bridge Account", FAGE flags the entire network.
6. **Plain-English Explanations:** For every flagged alert, the **SHAP Engine** reverse-engineers the ML math, and an LLM (guarded by NeMo) writes a human-readable Suspicious Activity Report (SAR) explaining exactly *why* the transaction was flagged.

---

## 3. The Analyst User Journey

FAGE is not a spreadsheet; it is an active command center. When a Level-1 Security Analyst logs in:

* **Live Feed:** Thanks to a real-time SSE (Server-Sent Events) connection, newly flagged transactions flash on their screen instantly. They do not need to refresh the page.
* **Investigation Workbench:** They click an alert to open the Workbench.
* **The Network Graph:** Instantly, the UI draws a visual map showing the sender, receiver, and any linked accounts. The analyst can physically see if they are dealing with an isolated scam or a massive money laundering network.
* **Reviewing the AI:** Next to the graph, the analyst reads the LLM-generated explanation. They see the exact mathematical reasons (e.g., "Account Age is 2 days (+0.4 risk)").
* **Decision Time:** The analyst clicks **"Mark as Resolved"** (False Positive) or **"Block / Escalate"** (Confirmed Fraud). 
* **The Feedback Loop:** That click isn't just an administrative task. It feeds directly back into the backend, instantly retraining the PU Engine's thresholds to make the AI smarter for the next transaction.

---

## 4. Fundamental Terminology Glossary

* **PU Learning (Positive-Unlabeled Learning):** A machine learning strategy that trains the AI on "Confirmed Fraud" and "Unknown Data" rather than assuming unknown data is safe. It is built to hunt down hidden criminals.
* **`c` factor (Label Frequency):** The estimated true percentage of fraud hiding in the "Unknown" data pool.
* **SPY Tolerance:** A technique where the system injects fake "spies" (known fraud) into the clean data to see if the model catches them. This helps perfectly calibrate the risk thresholds.
* **Differential Privacy (DP):** A mathematical protocol that injects calculated noise into data exports to guarantee that an individual's personal financial records can never be leaked or reverse-engineered by internal staff or attackers.
* **NeMo Guardrails:** The strict firewall placed around the LLM that writes the Suspicious Activity Reports (SARs). It ensures the AI never hallucinates fake money amounts or leaks PII (Personally Identifiable Information).
* **SHAP (SHapley Additive exPlanations):** The mathematical system used to explain the ML model's decisions to regulators, ensuring FAGE is never an illegal "Black Box".
