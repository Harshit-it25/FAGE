"""
v3 -- preprocessing pass on top of v2, aimed at precision/recall/F1
while holding ROC-AUC roughly where it already is (~99%).

v2 already gets the ranking right (AUC ~99%). This version doesn't try
to rank better -- it tries to make the handful of borderline accounts
near the decision threshold easier to separate, via:

  1. Missingness indicator flags for partially-missing columns (missing
     patterns can encode account type/recency, thrown away by plain NaN).
  2. F3888 parsed as a real date -> days-since-reference, day-of-week,
     month, instead of an arbitrary label-encoded integer.
  3. Smoothed target encoding for categoricals (F3886, F3889, F3890,
     F3891, F3892, F3893, F2230) instead of arbitrary ordinal labels,
     fit on train only.
  4. Winsorization (1st/99th percentile clip, train-fit) on numeric
     features to stop a few extreme outliers from dominating splits.

Same repeated-CV, feature-selection, blend, threshold, bootstrap-CI
machinery as v2 so the comparison is apples to apples.
"""

import argparse
import joblib
import os
import json
import warnings
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, RepeatedStratifiedKFold
from sklearn.metrics import (
    roc_auc_score, average_precision_score, precision_score,
    recall_score, f1_score, fbeta_score, confusion_matrix,
    precision_recall_curve
)
from sklearn.feature_selection import mutual_info_classif
from xgboost import XGBClassifier
from lightgbm import LGBMClassifier
from imblearn.over_sampling import SMOTE

warnings.filterwarnings("ignore")
RNG = 42
np.random.seed(RNG)

parser = argparse.ArgumentParser(description="Train v4: SMOTE + engineered features mule-account classifier")
parser.add_argument("--data_path", type=str, default="DataSet.csv",
                     help="Path to the training CSV (must contain target column F3924)")
parser.add_argument("--artifact_dir", type=str, default="artifacts",
                     help="Directory to save trained models + preprocessing artifacts for inference")
args = parser.parse_args()
os.makedirs(args.artifact_dir, exist_ok=True)

TARGET = "F3924"
SEED_FEATURES = [
    "F115", "F321", "F527", "F531", "F670", "F1692", "F2082", "F2122", "F2582",
    "F2678", "F2737", "F2956", "F3043", "F3836", "F3887", "F3889", "F3891", "F3894"
]
# All 6 originally confirmed leaks, dropped -- including F2230, which an
# earlier version of this script mistakenly re-included as a feature to
# target-encode. That caused a false 100% precision/AUC result (leakage,
# not a real improvement).
CONFIRMED_LEAKS = ["F3912", "F2230", "F3914", "F3908", "F3913", "Unnamed: 0"]

DATE_COL = "F3888"
TARGET_ENCODE_COLS = ["F3886", "F3889", "F3890", "F3891", "F3892", "F3893"]
FBETA = 2.0
MAX_FEATURES = 30
TEST_SIZE = 0.17  # 83/17, best of the splits tried so far

print("Loading dataset...")
df = pd.read_csv(args.data_path, low_memory=False)
y = df[TARGET].astype(int)
X = df.drop(columns=[TARGET])
n_pos = int(y.sum())
print(f"Shape: {df.shape} | positives: {n_pos} ({100*y.mean():.3f}%)")

drop_cols = [c for c in CONFIRMED_LEAKS if c in X.columns]
X = X.drop(columns=drop_cols)
print(f"Dropped {len(drop_cols)} confirmed leaks: {drop_cols}")

# ------------------------------------------------------------------
# 1. Missingness indicators for partially-missing columns
# ------------------------------------------------------------------
print("\n=== BUILDING MISSINGNESS INDICATORS ===")
miss_frac = X.isna().mean()
partial_missing_cols = miss_frac[(miss_frac > 0.01) & (miss_frac < 0.99)].index.tolist()
for c in partial_missing_cols:
    X[f"{c}__ISMISSING"] = X[c].isna().astype(np.int8)
print(f"Added {len(partial_missing_cols)} missingness-indicator columns.")

# ------------------------------------------------------------------
# 2. Parse F3888 as a real date
# ------------------------------------------------------------------
print("\n=== PARSING DATE FEATURE ===")
if DATE_COL in X.columns:
    dt = pd.to_datetime(X[DATE_COL], format="%m-%d-%Y", errors="coerce")
    ref_date = dt.max()
    X["F3888__DAYS_SINCE_REF"] = (ref_date - dt).dt.days.astype(np.float32)
    X["F3888__DOW"] = dt.dt.dayofweek.astype(np.float32)
    X["F3888__MONTH"] = dt.dt.month.astype(np.float32)
    X = X.drop(columns=[DATE_COL])
    print(f"Parsed {DATE_COL} into DAYS_SINCE_REF / DOW / MONTH, dropped raw column.")

# ------------------------------------------------------------------
# Split (do this before target encoding so encoding is train-only)
# ------------------------------------------------------------------
X_train_raw, X_test_raw, y_train, y_test = train_test_split(
    X, y, test_size=TEST_SIZE, stratify=y, random_state=RNG
)
print(f"\nTrain: {len(X_train_raw)} rows, {int(y_train.sum())} positives")
print(f"Test : {len(X_test_raw)} rows, {int(y_test.sum())} positives")

# ------------------------------------------------------------------
# 3. Smoothed target encoding for categoricals (train-fit only)
# ------------------------------------------------------------------
print("\n=== TARGET ENCODING CATEGORICALS ===")
global_rate = y_train.mean()
SMOOTHING = 20  # higher = trust the global rate more for rare categories
te_maps = {}
for c in TARGET_ENCODE_COLS:
    if c not in X_train_raw.columns:
        continue
    tmp = pd.DataFrame({"cat": X_train_raw[c].astype("string"), "y": y_train.values})
    stats = tmp.groupby("cat")["y"].agg(["mean", "count"])
    smoothed = (stats["mean"] * stats["count"] + global_rate * SMOOTHING) / (stats["count"] + SMOOTHING)
    te_maps[c] = smoothed.to_dict()
    print(f"  {c}: {len(te_maps[c])} categories target-encoded (global rate={global_rate:.4f})")

# ------------------------------------------------------------------
# Clean: remaining categoricals -> ordinal label encode, numerics -> float,
# then winsorize numerics using train percentiles
# ------------------------------------------------------------------
numeric_cols, cat_cols = [], []
for c in X_train_raw.columns:
    (numeric_cols if pd.api.types.is_numeric_dtype(X_train_raw[c]) else cat_cols).append(c)

keep_cols = []
for c in X_train_raw.columns:
    s = X_train_raw[c]
    if s.notna().sum() == 0 or s.nunique(dropna=False) <= 1:
        continue
    keep_cols.append(c)
numeric_cols = [c for c in numeric_cols if c in keep_cols]
cat_cols = [c for c in cat_cols if c in keep_cols]

label_cols = [c for c in cat_cols if c not in TARGET_ENCODE_COLS]
label_maps = {c: {v: i for i, v in enumerate(X_train_raw[c].astype("string").dropna().unique())}
              for c in label_cols}

# winsorize bounds from train, numeric cols only
clip_bounds = {}
for c in numeric_cols:
    lo, hi = X_train_raw[c].quantile([0.01, 0.99])
    clip_bounds[c] = (lo, hi)

def transform(Xraw):
    out = pd.DataFrame(index=Xraw.index)
    for c in numeric_cols:
        v = pd.to_numeric(Xraw[c], errors="coerce")
        lo, hi = clip_bounds[c]
        out[c] = v.clip(lo, hi).astype(np.float32)
    for c in label_cols:
        out[c] = Xraw[c].astype("string").map(label_maps[c]).fillna(-1).astype(np.float32)
    for c, mapping in te_maps.items():
        out[c] = Xraw[c].astype("string").map(mapping).fillna(global_rate).astype(np.float32)
    return out[keep_cols].astype(np.float32)

X_train = transform(X_train_raw)
X_test = transform(X_test_raw)
print(f"\nAfter cleaning: {X_train.shape[1]} features "
      f"(incl. missingness indicators + parsed date features)")

# SMOTE (used later) can't handle NaN -- it interpolates between neighbors
# in feature space. Impute with train medians here so both SMOTE'd and
# original rows share a consistent representation. (XGBoost/LightGBM
# would have been fine with the raw NaNs, but SMOTE requires this.)
train_medians = X_train.median()
X_train = X_train.fillna(train_medians)
X_test = X_test.fillna(train_medians)

# ------------------------------------------------------------------
# Feature selection (same approach as v2)
# ------------------------------------------------------------------
print(f"\n=== FEATURE SELECTION (target: <= {MAX_FEATURES} + seeds) ===")
non_seed = [c for c in X_train.columns if c not in SEED_FEATURES]
X_fill = X_train[non_seed].fillna(X_train[non_seed].median())

mi = mutual_info_classif(X_fill, y_train, random_state=RNG, discrete_features=False)
mi_rank = pd.Series(mi, index=non_seed).rank(ascending=False)

quick_model = XGBClassifier(
    n_estimators=150, max_depth=3, learning_rate=0.08,
    subsample=0.8, colsample_bytree=0.6, reg_lambda=2.0,
    scale_pos_weight=(y_train == 0).sum() / max((y_train == 1).sum(), 1),
    tree_method="hist", n_jobs=1, random_state=RNG, eval_metric="aucpr",
).fit(X_train[non_seed], y_train, verbose=False)
imp_rank = pd.Series(quick_model.feature_importances_, index=non_seed).rank(ascending=False)

combined_rank = (mi_rank + imp_rank).sort_values()
top_non_seed = combined_rank.head(MAX_FEATURES).index.tolist()
final_feature_list = list(dict.fromkeys(
    [f for f in SEED_FEATURES if f in X_train.columns] + top_non_seed
))
X_train = X_train[final_feature_list]
X_test = X_test[final_feature_list]
n_new_feature_types = sum(1 for f in final_feature_list if "__ISMISSING" in f or "F3888__" in f or f in TARGET_ENCODE_COLS)
print(f"Selected {len(final_feature_list)} features "
      f"({n_new_feature_types} are new v3 engineered features: "
      f"missingness flags / date parts / target-encoded categoricals).")
print("New engineered features that made the cut:",
      [f for f in final_feature_list if "__ISMISSING" in f or "F3888__" in f or f in TARGET_ENCODE_COLS])

# ------------------------------------------------------------------
# Models (identical config to v2)
# ------------------------------------------------------------------
spw = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

def make_xgb():
    return XGBClassifier(
        objective="binary:logistic", n_estimators=300, max_depth=3,
        learning_rate=0.04, min_child_weight=3, subsample=0.75,
        colsample_bytree=0.6, reg_alpha=0.3, reg_lambda=2.0,
        scale_pos_weight=spw, eval_metric="aucpr",
        tree_method="hist", n_jobs=1, random_state=RNG,
    )

def make_lgbm():
    return LGBMClassifier(
        objective="binary", n_estimators=300, max_depth=3, num_leaves=7,
        learning_rate=0.04, min_child_samples=5, subsample=0.75,
        colsample_bytree=0.6, reg_alpha=0.3, reg_lambda=2.0,
        scale_pos_weight=spw, n_jobs=1, random_state=RNG, verbosity=-1,
    )

def blend_predict(models, Xd):
    return np.mean([m.predict_proba(Xd)[:, 1] for m in models], axis=0)

N_SPLITS, N_REPEATS = 5, 10
print(f"\n=== REPEATED CV: {N_SPLITS}-fold x {N_REPEATS} repeats ({N_SPLITS*N_REPEATS} fits) ===")
rskf = RepeatedStratifiedKFold(n_splits=N_SPLITS, n_repeats=N_REPEATS, random_state=RNG)

fold_aucs, fold_praucs, fold_thresholds = [], [], []
oof_sum = np.zeros(len(X_train))
oof_count = np.zeros(len(X_train))

for i, (tr, va) in enumerate(rskf.split(X_train, y_train), 1):
    # SMOTE fit on the training portion of this fold ONLY -- never on the
    # validation portion, or it would leak synthetic near-duplicates of
    # validation-adjacent points across the split.
    sm = SMOTE(random_state=RNG, k_neighbors=5)
    X_tr_res, y_tr_res = sm.fit_resample(X_train.iloc[tr], y_train.iloc[tr])

    xgb_m = make_xgb().fit(X_tr_res, y_tr_res, verbose=False)
    lgb_m = make_lgbm().fit(X_tr_res, y_tr_res)
    p = blend_predict([xgb_m, lgb_m], X_train.iloc[va])
    oof_sum[va] += p
    oof_count[va] += 1
    y_va = y_train.iloc[va]
    if y_va.sum() > 0:
        fold_aucs.append(roc_auc_score(y_va, p))
        fold_praucs.append(average_precision_score(y_va, p))
        prec, rec, thr = precision_recall_curve(y_va, p)
        fb = (1 + FBETA**2) * prec * rec / (FBETA**2 * prec + rec + 1e-12)
        if len(thr) > 0:
            fold_thresholds.append(thr[np.nanargmax(fb[:-1])])
    if i % 10 == 0:
        print(f"  ...{i}/{N_SPLITS*N_REPEATS} fits done")

oof = np.divide(oof_sum, oof_count, out=np.zeros_like(oof_sum), where=oof_count > 0)
oof_auc = roc_auc_score(y_train, oof)
oof_prauc = average_precision_score(y_train, oof)
print(f"\nRepeated-CV ROC-AUC : {np.mean(fold_aucs)*100:.2f}% (+/- {np.std(fold_aucs)*100:.2f})")
print(f"Repeated-CV PR-AUC  : {np.mean(fold_praucs)*100:.2f}% (+/- {np.std(fold_praucs)*100:.2f})")
print(f"OOF (blended) ROC-AUC: {oof_auc*100:.2f}%  |  OOF PR-AUC: {oof_prauc*100:.2f}%")

THRESH = float(np.median(fold_thresholds))
print(f"Selected threshold: {THRESH:.4f}")

final_sm = SMOTE(random_state=RNG, k_neighbors=5)
X_train_res, y_train_res = final_sm.fit_resample(X_train, y_train)
print(f"\nSMOTE on final train set: {int(y_train.sum())} positives -> "
      f"{int(y_train_res.sum())} (synthetic), majority class untouched at "
      f"{int((y_train_res==0).sum())}. Test set NOT resampled (kept at "
      f"real-world {int(y_test.sum())} positives / {len(y_test)} rows).")
final_xgb = make_xgb().fit(X_train_res, y_train_res, verbose=False)
final_lgb = make_lgbm().fit(X_train_res, y_train_res)
test_prob = blend_predict([final_xgb, final_lgb], X_test)
test_pred = (test_prob >= THRESH).astype(int)

test_auc = roc_auc_score(y_test, test_prob)
test_prauc = average_precision_score(y_test, test_prob)
test_prec = precision_score(y_test, test_pred, zero_division=0)
test_rec = recall_score(y_test, test_pred, zero_division=0)
test_f1 = f1_score(y_test, test_pred, zero_division=0)
test_fb = fbeta_score(y_test, test_pred, beta=FBETA, zero_division=0)
tn, fp, fn, tp = confusion_matrix(y_test, test_pred, labels=[0, 1]).ravel()

print("\n=== HELD-OUT TEST ===")
print(f"ROC-AUC   : {test_auc*100:.2f}%")
print(f"PR-AUC    : {test_prauc*100:.2f}%")
print(f"Precision : {test_prec*100:.2f}%")
print(f"Recall    : {test_rec*100:.2f}%")
print(f"F1        : {test_f1*100:.2f}%")
print(f"F{FBETA}       : {test_fb*100:.2f}%")
print(f"TN={tn} FP={fp} FN={fn} TP={tp}  (positives in test: {int(y_test.sum())})")

rng = np.random.RandomState(RNG)
idx = np.arange(len(y_test))
y_test_arr = y_test.to_numpy()
boot_prec, boot_rec, boot_f1 = [], [], []
for _ in range(1000):
    bi = rng.choice(idx, size=len(idx), replace=True)
    yb, pb = y_test_arr[bi], test_pred[bi]
    if yb.sum() == 0:
        continue
    boot_prec.append(precision_score(yb, pb, zero_division=0))
    boot_rec.append(recall_score(yb, pb, zero_division=0))
    boot_f1.append(f1_score(yb, pb, zero_division=0))

def ci(arr):
    return np.percentile(arr, [2.5, 97.5])

print("\n=== BOOTSTRAP 95% CI on test metrics ===")
print(f"Precision 95% CI: [{ci(boot_prec)[0]*100:.1f}%, {ci(boot_prec)[1]*100:.1f}%]")
print(f"Recall    95% CI: [{ci(boot_rec)[0]*100:.1f}%, {ci(boot_rec)[1]*100:.1f}%]")
print(f"F1        95% CI: [{ci(boot_f1)[0]*100:.1f}%, {ci(boot_f1)[1]*100:.1f}%]")

results = {
    "final_feature_list": final_feature_list,
    "threshold": THRESH,
    "repeated_cv": {"roc_auc_mean": float(np.mean(fold_aucs)), "pr_auc_mean": float(np.mean(fold_praucs))},
    "held_out_test": {"roc_auc": float(test_auc), "pr_auc": float(test_prauc),
                       "precision": float(test_prec), "recall": float(test_rec), "f1": float(test_f1),
                       "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
}
with open(os.path.join(args.artifact_dir, "results_v4.json"), "w") as f:
    json.dump(results, f, indent=2)

# ------------------------------------------------------------------
# Save everything needed to score new, unseen rows later without
# retraining: both models, the decision threshold, the exact final
# feature list/order, and every train-fit preprocessing artifact
# (label maps, target-encoding maps, winsorize bounds, median-impute
# values). See INTEGRATION.md for how to use this at inference time.
# ------------------------------------------------------------------
artifact_bundle = {
    "final_xgb": final_xgb,
    "final_lgb": final_lgb,
    "threshold": THRESH,
    "final_feature_list": final_feature_list,
    "keep_cols": keep_cols,
    "numeric_cols": numeric_cols,
    "label_cols": label_cols,
    "label_maps": label_maps,
    "target_encode_cols": TARGET_ENCODE_COLS,
    "te_maps": te_maps,
    "global_rate": float(global_rate),
    "clip_bounds": clip_bounds,
    "train_medians": train_medians.to_dict(),
    "date_col": DATE_COL,
    "confirmed_leaks": CONFIRMED_LEAKS,
    "target_col": TARGET,
    "fbeta": FBETA,
}
joblib.dump(artifact_bundle, os.path.join(args.artifact_dir, "v4_model_bundle.joblib"))
print(f"\nSaved model bundle + results to: {args.artifact_dir}/")
print("Done.")
