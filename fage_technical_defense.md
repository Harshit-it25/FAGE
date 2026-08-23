# FAGE (Fraud Assessment & Governance Engine)
**Ultimate Technical Defense & Brutal Q&A**

> **Target Audience:** IIT Hyderabad Technical Panel / Compliance Auditors.
> **Objective:** A hardcore, unvarnished defense of the system's architecture, ML math, and security parameters. If you are grilled by a Principal Engineer or Data Scientist, the answers below are your absolute defense.

---

## 1. Core Architectural Specs
* **Concurrency & Streaming:** FastAPI running on an ASGI loop. SSE (Server-Sent Events) is used to push live alerts instead of WebSockets to maintain stateless HTTP multiplexing and firewall compatibility.
* **Database & Transactions:** Python SQLAlchemy with explicit ACID atomic transactions. Double-commits are blocked by setting `commit=False` on audit logging dependencies.
* **Graph Computations:** Computed in memory via bounded, $O(1)$ subsets using explicitly capped (`LIMIT 500`) SQL `OR` clauses across Hop-1 and Hop-2 relational queries to prevent memory exhaustion (OOM).

---

## 2. The Brutal Q&A Bank

### Category A: Machine Learning & Mathematics

**Q1: "In PU Learning, what happens if you set the `c` factor to 0 or 1?"**
> **Defense:** "If `c` is 0, the PU formula collapses into standard supervised learning because you are assuming there is 0% hidden fraud in the unlabeled set. If `c` is 1, the math breaks (division by zero in some estimators) because you are assuming the entire unlabeled set is 100% fraud, which implies legitimate users don't exist. We use the SPY technique to empirically bound `c` between 0.01 and 0.15 based on dataset distribution."

**Q2: "SHAP values assume feature independence. In financial fraud, 'Amount' and 'Velocity' are highly correlated. Doesn't this make your SHAP explanations mathematically flawed?"**
> **Defense:** "Tree-based SHAP (TreeExplainer), which is standard for Random Forests/XGBoost, intrinsically handles correlated features by calculating the marginal contribution across all possible feature permutations traversing the tree splits. While true mathematical independence is violated, the local accuracy (the sum of SHAP values strictly equals the exact model output) is guaranteed, satisfying regulatory explainability requirements."

**Q3: "If you query the system 100 times, doesn't your Differential Privacy noise cancel out, leaking the true data?"**
> **Defense:** "This is known as the Composition Theorem vulnerability. FAGE tracks the cumulative Epsilon ($\epsilon$) budget statefully across the session. Each query deducts from the global budget. Once the budget hits zero, the `dp_engine` triggers a hard block and refuses to output any more data until the budget resets (e.g., daily), making statistical averaging attacks impossible."

**Q4: "How do you detect Concept Drift? If scammers change their behavior, won't the model become useless?"**
> **Defense:** "The PU Engine is explicitly designed to combat concept drift. Our analysts use the `/feedback` route. When an analyst marks 'False Positive' or 'Escalated', it shifts the known-positive distribution in real-time. By re-evaluating the SPY tolerance dynamically against fresh Unlabeled data, the threshold automatically adjusts without requiring a full model retraining."

### Category B: Backend & Performance Architecture

**Q5: "Why did you use FastAPI instead of Django or Flask?"**
> **Defense:** "FAGE handles extreme concurrency for real-time SSE streaming. FastAPI uses ASGI (Asynchronous Server Gateway Interface), allowing non-blocking I/O operations. Flask uses WSGI, which blocks the thread per request. Furthermore, FastAPI deeply integrates with Pydantic, moving schema validation to the lowest C-level rust bindings via Pydantic v2, making payload validation orders of magnitude faster than Django serializers."

**Q6: "If the ML inference is CPU-bound, won't it freeze your FastAPI asynchronous event loop?"**
> **Defense:** "Exactly. A raw ML inference call would block the async loop. To prevent this, our `/inference` routes use FastAPI’s `run_in_threadpool()`. This offloads the heavy CPU blocking task (scoring the model) to a background thread, leaving the main thread free to handle thousands of concurrent SSE connections."

**Q7: "You are rendering a Graph of connected accounts. Graph traversals are notorious for OOM (Out Of Memory) crashes. How is this safe?"**
> **Defense:** "Originally, naive ORM queries would fetch the whole DB. We rewrote the `/correlate` route to execute highly restrictive SQLAlchemy queries. It only looks 1-hop and 2-hops out, explicitly capping the returned records at 500 via SQL `LIMIT`. The relational subset is loaded in $O(1)$ memory, completely eliminating OOM risks regardless of total database size."

**Q8: "What prevents a malicious user from uploading a 100GB CSV to your `/batch-score` endpoint and crashing the server?"**
> **Defense:** "We enforce a hard byte-read limit at the router level. Before allocating memory to parse the CSV/JSON, the FastAPI dependency evaluates the stream bytes. Anything over **5MB** throws a 413 Payload Too Large exception, strictly capping memory consumption and preventing DDOS via memory exhaustion."

### Category C: Frontend & Data Synchronization

**Q9: "How does the frontend receive live alerts? Are you just polling the database every 2 seconds?"**
> **Defense:** "Polling would DDOS our own database. We use **Server-Sent Events (SSE)**. The backend holds a lightweight TCP connection open to the client. When a new alert is generated, it is pushed downstream immediately. Unlike WebSockets, SSE operates over standard HTTP/1.1 or HTTP/2 multiplexing, making it highly resilient and natively supported by corporate firewalls."

**Q10: "If SSE is just HTTP, how are you authenticating the live stream? You can't pass custom headers in browser EventSource APIs."**
> **Defense:** "That is a known browser limitation. To secure the SSE stream without headers, our frontend `api.ts` extracts the JWT from local storage and appends it securely as a URL query parameter (`?token=`). The backend `auth.py` dependency intercepts this query parameter, validates the cryptographic signature, and opens the stream."

**Q11: "Why use `vis-network` for the graph instead of standard D3.js?"**
> **Defense:** "D3 is powerful but requires manual physics configurations for force-directed layouts. FAGE alerts need to render complex, multi-hop mule networks instantly. `vis-network` has a native Barnes-Hut physics engine that automatically stabilizes nodes. We optimized this by setting a deterministic `randomSeed: 42`, guaranteeing that the graph renders the exact same layout every time you refresh, avoiding visual jarring for analysts."

### Category D: Security & Compliance

**Q12: "Your database transactions. What happens if two analysts try to mark an alert 'Resolved' at the exact same millisecond?"**
> **Defense:** "We addressed a Double-Commit vulnerability in our `write_audit` logging. Previously, implicit commits caused database lock failures under concurrency. Now, the logging function enforces `commit=False` by default. The outer router scopes the entire state change and the audit log into a single SQLAlchemy atomic transaction, ensuring ACID compliance (Atomicity, Consistency, Isolation, Durability)."

**Q13: "What is your defense against adversarial 'Micro-Structuring' (e.g., trying to send ₹49,999 to bypass a ₹50,000 PAN limit)?"**
> **Defense:** "Our Triage Engine (`triage_policy.py`) specifically calculates an **'Evadable'** Boolean flag. It runs a micro-perturbation analysis behind the scenes. If adding or subtracting 5% to the transaction amount causes the ML model to flip its decision, FAGE realizes it is hovering on a critical boundary and forces a manual review, actively neutralizing structuring attacks."
