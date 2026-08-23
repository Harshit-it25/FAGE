# FAGE (Fraud Assessment & Governance Engine)
**Dedicated Security & Hardening Audit**

> **Target Audience:** Information Security Officers (CISO), Penetration Testers, and IIT Hyderabad Security Panel.
> **Objective:** A dedicated, brutal breakdown of exactly what security vulnerabilities existed, how they were mitigated, and the defensive architecture implemented to protect the FAGE system.

---

## 1. Denial of Service (DoS) & Memory Exhaustion Defenses

**Vulnerability: Database Memory Exhaustion (OOM) via Graph Traversal**
* **The Flaw:** The `/correlate` endpoint (which builds the Network Graph for the UI) previously executed a `db.query(AlertModel).all()` operation. As the database grew, this would attempt to load millions of rows into RAM simultaneously, triggering a massive Out Of Memory (OOM) crash and locking the server.
* **The Fix:** The route was completely rewritten to use highly restrictive SQLAlchemy relational queries. It now specifically filters for 1-hop and 2-hop accounts associated *only* with the target alert, and enforces a strict SQL `LIMIT 500`. The graph builds instantly in bounded $O(1)$ memory regardless of total database size.

**Vulnerability: CSV Bombing via Batch Inference**
* **The Flaw:** The `/batch-score` endpoint allowed unrestricted file uploads. An attacker (or a careless analyst) could upload a 10GB CSV file, causing the FastAPI server to crash while attempting to allocate RAM to parse the payload.
* **The Fix:** Implemented a strict **5MB byte-read limit** at the router dependency level. The server now checks the incoming stream size and immediately throws a `413 Payload Too Large` exception before the payload can enter working memory.

---

## 2. API Authentication & Real-Time Security

**Vulnerability: Unauthenticated Server-Sent Events (SSE)**
* **The Flaw:** The frontend relies on SSE (`EventSource`) to stream live alerts to the dashboard. However, native browser `EventSource` APIs strip out custom HTTP headers (like `Authorization: Bearer <token>`). This meant the live stream either dropped entirely or required bypassing the security gateway.
* **The Fix:** We implemented a secure token-exchange workaround in `api.ts`. The frontend extracts the active JWT from secure local storage and appends it dynamically as a URL query parameter (`/stream-alerts?token=<jwt>`). The backend `auth.py` dependency intercepts this parameter, cryptographically validates the JWT signature, and opens the stream without compromising the zero-trust architecture.

**Vulnerability: Payload Tampering & State Injection**
* **The Flaw:** Status update payloads (`PUT /alerts/{id}`) originally accepted any generic string. An attacker intercepting the API could inject malformed states or SQL-like syntax.
* **The Fix:** Hardened the payload validation using Pydantic v2 underlying Rust binaries. The `status` field is now strictly typed using `Literal['Open', 'Investigating', 'Escalated', 'Closed']`. Any payload deviating from this exact enum is killed instantly with a `422 Unprocessable Entity` error before it ever reaches the database layer.

---

## 3. Database Integrity & Concurrency

**Vulnerability: The "Double-Commit" Database Lock**
* **The Flaw:** When an analyst triggered an action, the system logged the action via `write_audit`. The logging function implicitly executed a `db.commit()`. Then, the parent router executed a second `db.commit()` to finalize the state change. Under high concurrency (multiple analysts working simultaneously), this triggered SQLite locking errors and race conditions, crashing the action.
* **The Fix:** Disabled the implicit `autocommit` on the audit logger. The outer FastAPI router now scopes the entire workflow (state change + audit log) into a single, atomic ACID transaction. If any part of the process fails, the entire transaction rolls back cleanly.

**Vulnerability: Risk Score Truncation**
* **The Flaw:** The database schema mapped `risk_score` to a standard integer format in early iterations, causing fractional probabilities (e.g., 0.85) to truncate or round inconsistently during DB reads.
* **The Fix:** Explicitly cast the `risk_score` schema to a `Float` type across SQLAlchemy, guaranteeing exact probability parity between the ML inference output and the database storage.

---

## 4. Privacy & Generative AI Security

**Feature: Differential Privacy ($\epsilon$ Budgeting)**
* **The Defense:** To prevent internal bad actors (or compromised analyst accounts) from reverse-engineering the transaction histories of individuals by scraping aggregate dashboards, FAGE utilizes a `dp_engine`. It injects statistically calibrated Laplace/Gaussian noise into aggregate metrics. The system statefully tracks the Epsilon privacy budget; if an attacker queries the system too rapidly in an attempt to average out the noise (Composition Theorem attack), the budget depletes and the system completely locks down exports.

**Feature: NeMo Guardrails (LLM Firewall)**
* **The Defense:** FAGE generates Suspicious Activity Reports (SARs) using an LLM. Left unguarded, an LLM could hallucinate fake monetary values or illegally leak Personally Identifiable Information (PII) from its training data. We implemented **NeMo Guardrails** as a deterministic firewall. The LLM is only permitted to read the exact JSON SHAP math outputs. Furthermore, the UI forces a mandatory red disclaimer on every AI-generated response, ensuring regulatory compliance by requiring a human "attestation" click before the report is legally filed.
