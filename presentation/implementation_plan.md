# FAGE Critical Fixes - Implementation Plan

The external reviewer's brutal assessment is **100% mathematically and structurally correct.** We shipped a live credential, we have a split-brain architecture rendering conflicting judgments, we left a fatal attribute error in our flagship demo feature, and our stats presentation is a mess. 

This plan addresses all five points before the IIT Hyderabad presentation.

## User Review Required

> [!CAUTION]
> **API Key Rotation Required:** I will remove the live `NVIDIA_API_KEY` from `backend/.env`, but **you MUST manually rotate this key in your NVIDIA dashboard**. Once a key is written to disk/zipped and sent around, it is compromised. Do not use that specific key again.

> [!WARNING]
> **Variance Acknowledgment:** The reviewer is right about `cv_metrics.json` (precision standard deviation is 0.115 on a tiny 20-sample validation set). I will not try to overfit this late; you must simply be prepared to answer: *"Yes, we operated on a heavily imbalanced dataset with limited known positive fraud cases, which is why we rely on human-in-the-loop and multi-hop graph context rather than raw classifier precision."*

## Open Questions

None. The fixes required are strictly structural and mathematically necessary.

## Proposed Changes

---

### Security (Credential Leak)

#### [MODIFY] [backend/.env](file:///C:/Users/Admin/Downloads/fage%20new/backend/.env)
- Remove the `NVIDIA_API_KEY` plaintext value.
- Add a dummy value/comment instructing the user to inject it via the environment.

---

### Core Risk Engine & Dependencies (Split-Brain Fix)

The app is currently confused between two completely different configurations. I will enforce a single source of truth: `model_metadata.json`.

#### [DELETE] [backend/per_model_cost_thresholds.json](file:///C:/Users/Admin/Downloads/fage%20new/backend/per_model_cost_thresholds.json)
- Delete this file entirely. It is a stale artifact driving the false `0.04` threshold.

#### [DELETE] [backend/metrics.json](file:///C:/Users/Admin/Downloads/fage%20new/backend/metrics.json)
#### [DELETE] [backend/val_metrics.json](file:///C:/Users/Admin/Downloads/fage%20new/backend/val_metrics.json)
#### [DELETE] [backend/models/results_v4.json](file:///C:/Users/Admin/Downloads/fage%20new/backend/models/results_v4.json)
- Delete all incompatible redundant JSON model files that conflict with the audited `v2_seed_forced_leak_audited` model.

#### [MODIFY] [backend/app/dependencies.py](file:///C:/Users/Admin/Downloads/fage%20new/backend/app/dependencies.py)
- Refactor the startup block that attempts to read `per_model_cost_thresholds.json`.
- Instead, read the `decision_threshold` directly from `model_metadata.json` so that `GLOBAL_DECISION_THRESHOLD` explicitly matches `0.42` at boot time.

---

### Governance Engine (Flagship Bug Fix)

#### [MODIFY] [backend/app/services/governance_service.py](file:///C:/Users/Admin/Downloads/fage%20new/backend/app/services/governance_service.py)
- **Fix:** Line 508 and 509 try to use `.get("amount")` on an SQLAlchemy `AlertModel` ORM object (which crashes the API with `AttributeError`).
- Change `target.get("amount")` to `target.amount`.
- Change `target.get("severity")` to `target.severity`.

## Verification Plan

### Automated Tests
- Run `pytest backend/tests/test_network_graph.py` to ensure the mule-hunting flagship test (`test_correlate_alert_returns_sender_and_receiver`) passes (currently failing).
- Run `pytest backend/tests/test_fage_security_regression.py` to verify no regressions in the security bounds.

### Manual Verification
- Re-run the zip script to ensure we produce a clean bundle.
