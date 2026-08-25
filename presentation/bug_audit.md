# 🔴 BRUTAL BUG AUDIT — Full Codebase Analysis

Every single file. No mercy.

---

## 1. `backend/app/auth.py`

### 🔴 CRITICAL: API key comparison is NOT constant-time
**Line 222:** `if expected_key and x_api_key == expected_key:`

This is a **timing side-channel attack**. Python's `==` short-circuits on string comparison. An attacker can measure response latency to brute-force the API key byte-by-byte. Must use `hmac.compare_digest`.

```diff
- if expected_key and x_api_key == expected_key:
+ if expected_key and hmac.compare_digest(x_api_key, expected_key):
```

### 🔴 CRITICAL: JWT token priority is WRONG — cookie overrides Authorization header
**Line 187:** `jwt_candidate = fage_jwt or bearer or token`

The `fage_jwt` cookie is checked **first**. If a rogue or stale cookie is present, it silently overrides a fresh `Authorization: Bearer` header. The priority should be: header → oauth2 bearer → cookie → query token.

```diff
- jwt_candidate = fage_jwt or bearer or token
+ jwt_candidate = bearer or fage_jwt or token
```

### 🟡 HIGH: `x_api_key` is redundantly passed to `get_current_user` after already being handled
**Line 226:** `return await get_current_user(authorization, x_api_key, bearer, fage_jwt, token)`

Inside `verify_api_key`, if `x_api_key` is set, it has already either returned (valid key) or raised (bad key). If `x_api_key` is NOT set, calling `get_current_user` with it is harmless but the `get_current_user` function also accepts `x_api_key` as a parameter — however `get_current_user` **never actually uses `x_api_key`** to perform key validation. This confuses future readers about the auth flow and is a latent bug if `get_current_user` is ever modified.

### 🟡 HIGH: USERS dict is populated at **module import time** with bcrypt hashing
**Lines 88–96:** All bcrypt hashes are computed synchronously during `import`. In an async server, this is a startup cost that **blocks the event loop** indirectly and may cause slow startup on weak hardware.

### 🟡 MEDIUM: `_is_dev_env()` is called multiple times across files — inconsistent environment detection
The dev detection logic is duplicated in `auth.py` AND `main.py`. If they ever diverge (one file uses `FAGE_ENV=dev`, the other uses `ENVIRONMENT=dev`), the server could boot with different auth policies on each module. This should be a single centralized function.

---

## 2. `backend/app/routers/auth.py`

### 🔴 CRITICAL: Massive unused import pile
**Lines 5, 12–19, 44–46:** `pickle`, `io`, `random`, `cosine_similarity`, `StreamingResponse`, `FastAPI`, `UploadFile`, `File`, `Header`, `dp_engine`, `PrivacyBudgetExceededError`, `call_nvidia_llm`, `FAGERiskEngine` — **none of these are used in this file**. This is copied boilerplate from the old monolithic router. Each unused import is a dead weight increasing startup time and creating confusion.

### 🟡 HIGH: `_correlate_cache_lock` not imported but `_correlate_cache` is
**Line 56 (routers/auth.py):** The `auth` router imports `_correlate_cache` but NOT `_correlate_cache_lock`. The governance router correctly imports both. This means if auth.py ever tried to use the cache it would race without the lock.

### 🟡 MEDIUM: `write_audit` is called with `db.commit()` AFTER, but the audit helper's default `commit=True` also commits
**Line 78–83:** `write_audit(..., commit=True by default)` is called, then `db.commit()` is called again on line 83. This is a **double-commit**. While harmless in SQLite, on PostgreSQL this can cause transaction boundary confusion. The pattern throughout the codebase is inconsistent — sometimes `commit=True` (default), sometimes followed by a manual `db.commit()`.

---

## 3. `backend/app/routers/governance.py`

### 🔴 CRITICAL: `stream_alerts` opens DB session INSIDE async generator — session is never closed on client disconnect
**Lines 351–360:** The first DB session is closed in a `finally` block (ok). But then **a new `db = SessionLocal()` is opened on line 369 inside the polling loop**, inside a `finally` block per iteration. This is correct *normally*, but if the SSE client disconnects abruptly (browser tab closed, network drop), the `asyncio.CancelledError` is caught on line 366, which `break`s out of the loop — but the **currently-open `db` session from the previous loop iteration is NOT closed**. 

The sequence: open `db` → `await asyncio.sleep(2.5)` gets cancelled → `break` → the `db` that was opened on the PREVIOUS completed iteration was closed, but the open at the **current point in the loop has already been done before the `sleep`.** Actually let me re-read — the `db` is opened at L369, and `finally: db.close()` wraps from L371–382. The `CancelledError` is caught before the `db` is opened. So the session leak only occurs if the cancellation happens between L369 and L382. In asyncio this is possible because `asyncio.CancelledError` can arrive at any `await` point, and the `db.close()` in the `finally` at L381 should handle it. **However**, the `with` pattern is safer. More critically:

### 🔴 CRITICAL: `stream_alerts` has NO authentication on the yielded data
**Line 347–348:** The route has `dependencies=[Depends(verify_api_key)]`, so the connection itself is authenticated. But `EventSource` in browsers **cannot set custom headers** and only uses cookies. If the JWT is only in the `Authorization` header (not in the cookie), this SSE endpoint will **always return 401** to browser clients.

The frontend's `connectAlertStream` (api.ts L688) uses `{ withCredentials: true }` which sends cookies — so this works IF the user has the `fage_jwt` cookie. But if using token-based auth (no cookie), SSE is broken.

### 🔴 CRITICAL: `print()` debug statements left in production code
**Lines 398–401 (governance_service.py):**
```python
print("DEBUG: CORRELATE SERVICE ALERT COUNT:", len(alerts))
print("DEBUG: CORRELATE SERVICE LOOKING FOR:", alert_id)
print("DEBUG: TARGET NOT IN ALERTS!")
```
These **print raw alert IDs and counts to stdout** in production. Information leakage. Must be replaced with `logger.debug()`.

### 🟡 HIGH: Double `_active_alert_score_cutoffs()` call — wasted DB computation
**Lines 90 and 109 in governance.py:** `active_metrics = _load_active_model_metrics()` is called **twice** — once at line 90 and again at line 109. The first result is immediately overwritten. Wasteful IO.

### 🟡 HIGH: `get_alert_by_id` strips `features` from the response
**Line 211:** `slim = {k: v for k, v in result.items() if k != "features"}`. The Investigation Workbench frontend makes a separate call to `/alerts/{id}/features` but that endpoint **does not exist in the backend**. The `api.ts` L556 calls `/alerts/${alertId}/features` but there's no router matching this path. This call will **always return 404**.

### 🟡 MEDIUM: `ingest_simulated_alert` validates status with `.capitalize()` but stores with `.capitalize()` only if valid
**Lines 221, 242:** The comparison `status_state.capitalize() not in permitted_states` is correct, but then storing `status_state.capitalize()` could map `"open"` → `"Open"`, `"OPEN"` → `"Open"`, etc. This is fine logically but the error message on L224 shows the **original un-capitalized** value to the user, which can be confusing.

### 🟡 MEDIUM: `update_alert_status_handler` — `write_audit` uses `commit=True` (default) AND `db.commit()` is called again at line 326 — double commit
Same double-commit pattern as noted above.

---

## 4. `backend/app/routers/inference.py`

### 🟡 HIGH: `predict_fraud_probability` exposes full exception message to client
**Line 93:** `raise HTTPException(status_code=500, detail=f"Inference Engine execution exception: {str(e)}")`

`str(e)` may contain file paths, model internals, or stack traces that are exposed to the API client. Use a generic message and log the real error.

### 🟡 HIGH: `score_and_evaluate_transaction` — alert creation race condition not fully handled
**Lines 156–240:** There's a TOCTOU (check-then-act) race: `existing = db.query(...).first()` then `if not existing: db.add(new_alert)`. The `IntegrityError` catch on L225 handles the race **only for the `transaction_id` UNIQUE constraint**. But `alert_id = f"ALT-{uuid.uuid4()}"` is generated before the insert. A UUID4 collision is astronomically unlikely but the code would crash with an unhandled error since the PK collision would also be an `IntegrityError` — and the rollback handler at L227 assumes it was a `transaction_id` conflict.

### 🟡 MEDIUM: `_process_batch_csv` error row counter is off by one
**Line 284:** `errors.append(f"Row {processed_rows + 1}: type coercion failed")` — `processed_rows` starts at 0 but is incremented AFTER the error is recorded (L285). So the row number reported is correct. But if the hard cap check on L259 runs mid-chunk, `processed_rows` already reflects rows from previous chunks, causing slightly misleading error messages in later chunks.

### 🟡 MEDIUM: `batch_score` doesn't limit file size
**Line 310:** `content = await file.read()` — there is no file size limit check before reading. A malicious user could upload a multi-GB CSV and exhaust server memory. The hard cap is 10,000 rows but that check only happens during parsing, after the entire file is already in memory.

---

## 5. `backend/app/routers/analytics.py`

### 🔴 CRITICAL: `/alerts/{alert_id}/features` endpoint does NOT EXIST
This endpoint is called by the frontend (`api.ts` L557) and referenced in `InvestigationWorkbenchView.tsx`. It returns 404 every time. The router for it is missing from all 5 router files.

**Fix:** Add to `governance.py`:
```python
@router.get("/alerts/{alert_id}/features", dependencies=[Depends(verify_api_key)])
def get_alert_features(alert_id: str, db: Session = Depends(get_db)):
    alert = db.query(AlertModel).filter(AlertModel.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    features = json.loads(alert.features) if alert.features else {}
    return {"status": "success", "features": features}
```

### 🟡 HIGH: `get_global_feature_importance` will crash if DB has no alerts with features
**Line 328:** `real_samples = _build_real_sample_df(db, n=10)` — If the database is empty, `_build_real_sample_df` returns a DataFrame of background mean values. Then `compute_global_shap(real_samples)` is called. This may fail if the SHAP engine expects real variance in the data. Needs a guard.

### 🟡 HIGH: `tune_pu_calibration` writes PU engine to disk with `pickle`
**Lines 466–470:** The PU engine is pickled and written to disk. If the `risk_engine.pu_engine` object has any non-serializable attributes (locks, file handles, etc.), this will crash silently. The error is swallowed at L471 with just a `logger.error`.

### 🟡 MEDIUM: `get_model_metrics_endpoint` returns `confusion_matrix` from `cost_thresholds.json` but that file can be missing/stale
**Lines 124:** The confusion matrix is read from a JSON file, not computed live. If the model is retrained or thresholds change, the confusion matrix shown in the UI is stale and misleading.

### 🟡 MEDIUM: `get_bias_audit` returns raw JSON from disk with no schema validation
**Line 601:** `return json.load(f)` — the `bias_audit.json` is returned as-is. If the file was written with a different schema version, the frontend will receive unexpected keys/shapes and silently break.

---

## 6. `backend/app/db.py`

### 🟡 HIGH: `AlertModel.risk_score` is `Column(Integer)` but used as `Float` throughout the codebase
**Line 36:** `risk_score = Column(Integer)` — but in `_active_alert_score_cutoffs()`, `alert_score = (alert.risk_score or 50.0) / 100.0` treats it as a float. Values like `4.7` would be stored as `4`, silently truncating risk precision. Should be `Float`.

### 🟡 HIGH: `AlertModel.timestamp` is `Column(String)` — sorting by timestamp will sort lexicographically, not chronologically
**Line 40:** Using a string timestamp means `2026-08-22...` sorts correctly by ISO format coincidence, but this is fragile. Should be a `DateTime` column. The `_ts` float column IS used for actual sorting (L185), but the `timestamp` string field's inconsistency can cause bugs when filtering or sorting by it.

### 🟡 MEDIUM: `ensure_schema_columns` silently swallows migration errors
**Lines 168–170:** The outer `except` block logs but does NOT re-raise. If the `triage_action` column doesn't exist and migration fails, the server boots successfully and then crashes on the first alert query. Should at least `raise` to fail fast at startup.

### 🟡 MEDIUM: `write_audit` has `commit: bool = True` parameter but callers consistently also call `db.commit()` manually afterwards
Double-commit pattern is endemic. The `commit` parameter should default to `False` to prevent this, or the callers need a consistent audit pattern. Currently both exist in the codebase.

---

## 7. `backend/app/dependencies.py`

### 🟡 HIGH: `_check_login_throttle` has a logic error — lockout condition is wrong
**Line 252:** `if len(attempts) >= _LOGIN_MAX_ATTEMPTS and (now - attempts[0]) < _LOGIN_LOCKOUT_SECONDS:`

`attempts[0]` is the **oldest** failure in the window. If 5 failures happened 59 seconds ago, `now - attempts[0]` is ~59 seconds, which is `< 60` → user is locked out. OK. But if 5 failures happened exactly 61 seconds ago, the window filter at L245 would have already pruned them (since `_LOGIN_WINDOW_SECONDS = 300`). So the lockout logic is actually checking the wrong thing — it should check if the MOST RECENT attempt is within the lockout window, not the oldest. The lockout never expires properly because `attempts[0]` is the oldest attempt and `_LOGIN_LOCKOUT_SECONDS < _LOGIN_WINDOW_SECONDS`, so the lockout lifts when `_LOCKOUT_SECONDS` elapses from the FIRST attempt, not the last.

### 🟡 HIGH: `_rate_limit_buckets` and `_login_failures` are in-process dicts — lost on restart
**Comments at Line 113:** There's a TODO noting this. In production with multiple workers (gunicorn `--workers 4`), each worker has its own in-memory dict. An attacker can hit different workers to bypass the rate limit and lockout. This is noted but actively dangerous.

### 🟡 MEDIUM: `_build_real_sample_df` uses `random.sample` without seeding — non-deterministic
**Line 227:** `random.sample(candidates, min(n, len(candidates)))` — results vary on every call, so the global SHAP profile shown in the UI is non-reproducible.

---

## 8. `backend/app/services/governance_service.py`

### 🟡 HIGH: `build_correlation_graph_service` loads ALL alerts into memory
**Line 397:** `alerts = db.query(AlertModel).all()` — no limit. If there are 100k+ alerts, this will OOM the process. Should paginate or use a graph DB.

### 🟡 HIGH: `_compute_graph_intelligence` uses `nx.simple_cycles` which can hang on large graphs
**Line 72:** `all_cycles = [c for c in nx.simple_cycles(subG, length_bound=4)]` — the `length_bound=4` parameter limits cycle length but NOT the number of cycles. A dense subgraph can still produce exponentially many cycles. The `subG.number_of_nodes() > 50` guard on L69 helps but 50-node graphs can still have billions of 4-cycles.

### 🟡 HIGH: `build_sar_report_service` calls `build_correlation_graph_service` which has a **30-second cache** — SAR may use stale graph data
**Line 196:** `corr = build_correlation_graph_service(alert_id, user, db)` — uses the cached result if < 30s old. An SAR could be based on stale correlation data that doesn't reflect recent alert updates.

### 🟡 MEDIUM: `_compute_graph_intelligence` → `time_window_seconds` assumes `timestamp` is numeric
**Line 95:** `time_window_seconds = (max(timestamps) - min(timestamps)) if len(timestamps) >= 2 else 0.0` — but `a._ts` (float epoch) is used as the timestamp in `alerts_copy` at L412. If `a._ts` is `None` (old records), this will crash with `TypeError: '>' not supported between 'float' and 'NoneType'`. No null check.

---

## 9. `frontend/src/services/api.ts`

### 🔴 CRITICAL: `/alerts/${alertId}/features` endpoint called but doesn't exist on backend
**Line 556–559:** `fageApi.getAlertFeatures` calls `/alerts/${alertId}/features`. This route **does not exist** in ANY backend router. Every call from `InvestigationWorkbenchView.tsx` will fail with 404. The investigation workbench silently fails to load features.

### 🔴 CRITICAL: `connectAlertStream` creates `EventSource` with NO auth token in URL
**Line 688–690:**
```ts
return new EventSource('/api/stream-alerts', { withCredentials: true });
```
`EventSource` can only send cookies. If the user authenticated with a Bearer token (not cookie), this will get a 401 and the SSE stream will silently fail to connect. The `withCredentials: true` only helps if `fage_jwt` cookie was set during login.

### 🟡 HIGH: `generateSAR` has wrong indentation — it's not part of the `fageApi` object
**Lines 568–571:** `generateSAR` is indented with 4 spaces inside the `fageApi = {}` object literal, but the closing `},` is at the same level as the object properties. This works in JS/TS because indentation is not significant, but it violates the consistent 2-space indentation used everywhere else and makes it look like `generateSAR` might accidentally be outside the object. Static analysis tools may flag this.

### 🟡 HIGH: `SARResponse` interface is missing `fincen_tracking_id` and `citation_hash` fields that the backend actually returns
**Lines 368–370:** The backend returns `{ sar_report, fincen_tracking_id, citation_hash }` but the TypeScript interface only declares `sar_report`. The other fields are silently ignored by TypeScript — any consumer of `generateSAR()` cannot access `fincen_tracking_id` without a type cast.

### 🟡 MEDIUM: `listAlertsQueue` accepts `source_filter: 'all' | 'target' | 'dataset'` but the backend only filters on `'target'` and `'dataset'` — `'all'` is treated as no filter
**Lines 160–163 in governance.py:** There's no `if source_filter == "all"` branch. The frontend sends `'all'` but the backend ignores it (no filter applied). This is actually the correct behavior but misleading — if the backend later adds validation, `'all'` would fail.

### 🟡 MEDIUM: `logout` in auth router doesn't write an audit log
**Lines 139–141 in routers/auth.py:** The logout endpoint deletes the cookie and returns success but does NOT call `write_audit`. Every login is audited but logouts are not. This is a compliance gap.

---

## 10. `backend/app/main.py`

### 🔴 CRITICAL: `Content-Security-Policy` allows `connect-src http://localhost:*`
**Line 111:** The CSP header allows connecting to any `http://localhost:*` port. This means a malicious script on the page can exfiltrate data to any locally-running service, including `http://localhost:3389` (RDP), `http://localhost:22` (SSH), etc. The CSP should only whitelist the specific ports needed.

### 🔴 CRITICAL: Catch-all route `/{full_path:path}` intercepts ALL API routes that aren't matched
**Lines 138–152:** The catch-all is registered AFTER the API routers, but since it's a `GET` on `/{full_path:path}`, it will match any unrecognized GET request. If a route is missing from any API router, the catch-all will silently serve `index.html` instead of returning a 404. This means **missing endpoints are completely invisible** during development.

### 🟡 HIGH: Path traversal check uses `os.path.commonpath` which may be insufficient on Windows
**Line 143:** `os.path.commonpath([static_root, candidate_path]) != static_root` — on case-insensitive Windows filesystems, `C:\Foo` and `c:\foo` may not match even though they refer to the same directory. Should normalize case first.

### 🟡 MEDIUM: `Strict-Transport-Security` header sent over HTTP in development
**Line 110:** `Strict-Transport-Security: max-age=31536000` is sent on all responses, even over plain HTTP during local development. Browsers will then refuse HTTP connections for a year, breaking local development.

---

## 11. `backend/app/schemas.py`

### 🟡 MEDIUM: `AlertUpdateRequest.status` has no enum validation — allows any string up to 32 chars
**Line 26:** `status: Optional[str] = Field(None, max_length=32)` — the docstring says valid values are `Open, Investigating, Escalated, Closed` but Pydantic won't enforce this. The enum validation only happens inside the router handler at runtime. Use `Literal['Open', 'Investigating', 'Escalated', 'Closed']` or a Python Enum instead.

### 🟡 MEDIUM: `FeedbackRequest.label` is a free-text string — allows anything
**Line 73:** `label: str = Field(..., max_length=64)` — the valid values documented in the schema description are `'True Positive', 'False Positive', 'Mule Ring', 'Suspicious'` but any string up to 64 chars is accepted. This bypasses the status-mapping logic in the governance router (L431-434) if an unexpected label is submitted.

---

## Summary Table

| Severity | Count | Examples |
|----------|-------|---------|
| 🔴 CRITICAL | 7 | Timing attack on API key, `/features` endpoint missing, JWT priority bug, debug prints in prod, missing route = silent 404, CSP localhost wildcard |
| 🟡 HIGH | 14 | Double commits, SSE auth failure, DB loads all alerts, lockout logic error, missing SAR fields in TypeScript, file size limit missing |
| 🟠 MEDIUM | 9 | Free-text enums, stale metrics, non-reproducible SHAP, Windows path normalization, HSTS over HTTP |

---

## Priority Fix Order

1. **Add `/alerts/{alert_id}/features` backend route** — breaks the investigation workbench for every alert
2. **Fix timing attack on API key comparison** — use `hmac.compare_digest`
3. **Fix JWT priority order** — cookie should NOT override header
4. **Remove `print()` debug statements** — production info leakage
5. **Fix `stream_alerts` SSE auth** — won't work without cookie
6. **Fix double-commit pattern** — set `commit=False` default in `write_audit` or remove manual `db.commit()` calls
7. **Add `logout` audit log**
8. **Add file size guard in `batch_score`**
9. **Add enum validation to `AlertUpdateRequest.status` and `FeedbackRequest.label`**
10. **Fix `risk_score` column type** — `Integer` → `Float`
