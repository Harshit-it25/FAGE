# v4 (Stability-Free Selection + SMOTE) — Integration Guide

This is the current best-performing mule/suspicious-account classifier for
Problem Statement 2 (target column `F3924`, seed features per the
organizer PDF). Held-out test result on an 83/17 split:

| Metric | Value |
|---|---|
| ROC-AUC | 99.88% |
| PR-AUC | 86.38% |
| Precision | 84.62% |
| Recall | 78.57% |
| F1 | 81.48% |

Bootstrap 95% CI (14 test positives — treat as an estimate, not exact):
Precision 60.0–100.0%, Recall 53.3–100.0%, F1 60.8–94.7%.

## What's in this package

```
train_v4_smote.py    # trains both models + saves an inference bundle
predict.py            # scores new rows using the saved bundle
requirements.txt
INTEGRATION.md         # this file
```

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

## 2. Train (or retrain on updated data)

```bash
python train_v4_smote.py --data_path /path/to/DataSet.csv --artifact_dir artifacts
```

This does the following, in order, and prints metrics at each stage:

1. Drops 6 confirmed data leaks (`F3912`, `F2230`, `F3908`, `F3913`,
   `F3914`, `Unnamed: 0`) — **do not remove this step or reintroduce
   these columns as features.** They were independently verified as
   leaks (near-perfect univariate correlation/purity with the target),
   and re-including any of them produces false near-100% scores.
2. Adds missingness-indicator flags, parses the `F3888` date field into
   recency/day-of-week/month, target-encodes 6 categorical columns
   (train-fit only), and winsorizes numeric outliers (train-fit only).
3. Selects ~48 features (18 organizer-specified seed features + ~30
   selected by mutual information + XGBoost importance).
4. Trains an XGBoost + LightGBM blend with **SMOTE applied only to the
   training fold in each CV split, and only to the final training set**
   — never to validation or test data. This is important: SMOTE before
   the train/test split, or inside a step that touches held-out data,
   silently inflates every metric.
5. Picks a decision threshold via repeated stratified 5-fold × 10-repeat
   CV (50 fits), optimizing F-beta (beta=2.0, recall-weighted — change
   `FBETA` at the top of the script if your review-capacity tradeoff is
   different).
6. Evaluates on a held-out 17% test split and reports a bootstrap 95%
   CI on precision/recall/F1 (important given the small positive count
   — a single point estimate is not reliable on its own).
7. Saves `artifacts/v4_model_bundle.joblib` (both trained models + every
   preprocessing artifact needed to score new data) and
   `artifacts/results_v4.json` (metrics).

## 3. Score new/incoming rows

```bash
python predict.py --input new_accounts.csv --artifact_dir artifacts --output scored.csv
```

Output adds two columns: `fraud_probability` (blended model score,
0–1) and `fraud_flag` (0/1, thresholded at the value picked during
training).

**Input schema requirement:** `new_accounts.csv` must have the same raw
F-code columns as the original training data (does not need the target
column `F3924` — it's dropped if present). The `F3888` date column must
use the same `M-D-YYYY` string format.

## 4. Integrating into a larger pipeline (e.g. a FastAPI/backend service)

Two integration patterns, pick based on your architecture:

**A. Batch scoring (simplest)** — call `predict.py` as a subprocess or
import its logic directly; run on a schedule or on-demand against a
CSV/DataFrame export from your data warehouse.

**B. In-process scoring (for a live API)** — load the bundle once at
service startup and reuse the transform logic from `predict.py` as a
function, e.g.:

```python
import joblib

bundle = joblib.load("artifacts/v4_model_bundle.joblib")

def score_accounts(df: pd.DataFrame) -> pd.DataFrame:
    # reuse the preprocessing block from predict.py (lines building `out`)
    # then:
    prob = (bundle["final_xgb"].predict_proba(X_score)[:, 1] +
            bundle["final_lgb"].predict_proba(X_score)[:, 1]) / 2.0
    return prob >= bundle["threshold"]
```

Load `bundle` once (it's a few MB) — do not reload it per request.

## 5. Known limitations to carry into the main codebase

- **Small positive count (81 total across the whole dataset).** Metrics
  above have real, wide confidence intervals. Don't present precision/
  recall as exact — surface the CI or at least caveat it in any UI/report
  built on top of this.
- **`F3888__DAYS_SINCE_REF` reference date is batch-relative in
  `predict.py`** (defaults to the max date in whatever batch you're
  scoring). If you score data in small batches over time, this will
  drift — either always score in one batch with historical context, or
  hardcode a fixed reference date consistent with what was used at
  training time before deploying to production.
- **Retraining:** if the organizers provide an updated/larger dataset,
  rerun `train_v4_smote.py` from scratch — do not attempt to
  incrementally update the saved bundle, since feature selection,
  target-encoding maps, and winsorization bounds are all data-dependent.
- **Threshold (`0.42`-ish, exact value printed at train time and stored
  in the bundle) is F2-optimized (recall-weighted).** If the review team
  wants fewer false positives at the cost of missing some cases, retrain
  with `FBETA` set closer to `0.5` in `train_v4_smote.py`.
