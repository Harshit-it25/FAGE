"""
Score new rows with the trained v4 bundle (train_v4_smote.py output).

Usage:
    python predict.py --input new_rows.csv --artifact_dir artifacts --output scored.csv

Input CSV must have the SAME raw columns as the original training data
(same F-codes, same F3888 date format "M-D-YYYY"). It does NOT need the
target column (F3924) -- if present, it's ignored.
"""

import argparse
import joblib
import numpy as np
import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument("--input", type=str, required=True, help="CSV of new rows to score")
parser.add_argument("--artifact_dir", type=str, default="artifacts")
parser.add_argument("--output", type=str, default="scored.csv")
args = parser.parse_args()

bundle = joblib.load(f"{args.artifact_dir}/v4_model_bundle.joblib")

df = pd.read_csv(args.input, low_memory=False)
if bundle["target_col"] in df.columns:
    df = df.drop(columns=[bundle["target_col"]])

# Drop confirmed leaks if present (defensive -- they shouldn't be used as inputs)
df = df.drop(columns=[c for c in bundle["confirmed_leaks"] if c in df.columns])

# Recreate missingness indicators (same convention as training: name__ISMISSING)
missing_ind_cols = [c for c in bundle["keep_cols"] if c.endswith("__ISMISSING")]
for c in missing_ind_cols:
    base = c[: -len("__ISMISSING")]
    if base in df.columns:
        df[c] = df[base].isna().astype(np.int8)
    else:
        df[c] = 0  # base column missing entirely -> can't tell, default 0

# Recreate date-derived features
date_col = bundle["date_col"]
if date_col in df.columns:
    dt = pd.to_datetime(df[date_col], format="%m-%d-%Y", errors="coerce")
    if "F3888__DAYS_SINCE_REF" in bundle["keep_cols"]:
        # NOTE: reference date is not stored in the bundle (v1 limitation) --
        # for consistent scoring across batches, pass the SAME reference
        # date used at train time, or extend the bundle to store it.
        # Defaulting to the max date seen in this scoring batch.
        ref_date = dt.max()
        df["F3888__DAYS_SINCE_REF"] = (ref_date - dt).dt.days.astype(np.float32)
    if "F3888__DOW" in bundle["keep_cols"]:
        df["F3888__DOW"] = dt.dt.dayofweek.astype(np.float32)
    if "F3888__MONTH" in bundle["keep_cols"]:
        df["F3888__MONTH"] = dt.dt.month.astype(np.float32)

out = pd.DataFrame(index=df.index)
for c in bundle["numeric_cols"]:
    if c not in df.columns:
        out[c] = bundle["train_medians"].get(c, 0.0)
        continue
    v = pd.to_numeric(df[c], errors="coerce")
    lo, hi = bundle["clip_bounds"][c]
    out[c] = v.clip(lo, hi).astype(np.float32)

for c in bundle["label_cols"]:
    if c not in df.columns:
        out[c] = -1.0
        continue
    out[c] = df[c].astype("string").map(bundle["label_maps"][c]).fillna(-1).astype(np.float32)

for c in bundle["target_encode_cols"]:
    if c not in bundle["te_maps"]:
        continue
    mapping = bundle["te_maps"][c]
    if c not in df.columns:
        out[c] = bundle["global_rate"]
        continue
    out[c] = df[c].astype("string").map(mapping).fillna(bundle["global_rate"]).astype(np.float32)

out = out[bundle["keep_cols"]].astype(np.float32)
train_medians = pd.Series(bundle["train_medians"])
out = out.fillna(train_medians)

X_score = out[bundle["final_feature_list"]]

prob_xgb = bundle["final_xgb"].predict_proba(X_score)[:, 1]
prob_lgb = bundle["final_lgb"].predict_proba(X_score)[:, 1]
prob = (prob_xgb + prob_lgb) / 2.0
pred = (prob >= bundle["threshold"]).astype(int)

result = df.copy()
result["fraud_probability"] = prob
result["fraud_flag"] = pred
result.to_csv(args.output, index=False)
print(f"Scored {len(result)} rows -> {args.output}")
print(f"Flagged as suspicious: {int(pred.sum())} / {len(pred)} "
      f"(threshold={bundle['threshold']:.4f})")
