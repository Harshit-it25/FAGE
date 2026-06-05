import os
import sys
import json
import joblib
import warnings
import pickle
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import shap
import matplotlib.pyplot as plt

from sklearn.model_selection import (
    train_test_split,
    StratifiedKFold,
    cross_val_score
)

from sklearn.feature_selection import (
    VarianceThreshold,
    SelectKBest,
    mutual_info_classif
)

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score
)

from sklearn.ensemble import IsolationForest

from imblearn.over_sampling import SMOTE

from xgboost import XGBClassifier

# Adjust path to enable importing from FAGE package modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.ml.preprocessing import FAGEPreprocessor
from app.ml.feature_selection import FAGEFeatureSelector

# ==========================================
# DATASET
# ==========================================

DATASET_PATH = "/content/drive/MyDrive/DataSet.csv"

# Fallback path configurations for local run convenience
if not os.path.exists(DATASET_PATH):
    local_fallbacks = [
        "C:\\Users\\harsh\\Downloads\\DataSet.csv",
        "DataSet.csv",
        "../DataSet.csv",
        "backend/DataSet.csv"
    ]
    for p in local_fallbacks:
        if os.path.exists(p):
            DATASET_PATH = p
            break

print("Target Dataset Path:", DATASET_PATH)

df = pd.read_csv(DATASET_PATH)

print("Original Shape:", df.shape)

# ==========================================
# REMOVE LEAKAGE
# ==========================================

df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

TARGET = "F3924"

LEAKAGE_COLS = [
    "F3912",
    "F3920",
    "F3921",
    "F3922",
    "F3923"
]

existing = [c for c in LEAKAGE_COLS if c in df.columns]

df.drop(columns=existing, inplace=True)

# ==========================================
# FEATURES
# ==========================================

X = df.drop(columns=[TARGET])
y = df[TARGET]

for col in X.columns:
    X[col] = pd.to_numeric(
        X[col],
        errors="coerce"
    )

X = X.fillna(X.median())

print(y.value_counts())

# ==========================================
# VARIANCE FILTER
# ==========================================

vt = VarianceThreshold(0.01)

X_vt = vt.fit_transform(X)

selected_after_vt = X.columns[
    vt.get_support()
]

print("After Variance:", X_vt.shape)

# ==========================================
# FEATURE SELECTION
# ==========================================

TOP_K = 500

selector = SelectKBest(
    mutual_info_classif,
    k=min(TOP_K, X_vt.shape[1])
)

X_selected = selector.fit_transform(
    X_vt,
    y
)

final_features = selected_after_vt[
    selector.get_support()
]

print(
    "Selected Features:",
    len(final_features)
)

# Convert X_selected back to DataFrame to preserve feature names for SHAP
X_selected_df = pd.DataFrame(X_selected, columns=final_features)

# ==========================================
# CROSS VALIDATION
# ==========================================

cv_model = XGBClassifier(
    n_estimators=500,
    max_depth=5,
    learning_rate=0.03,
    subsample=0.8,
    colsample_bytree=0.8,
    scale_pos_weight=111,
    random_state=42,
    eval_metric="logloss",
    n_jobs=-1
)

cv = StratifiedKFold(
    n_splits=5,
    shuffle=True,
    random_state=42
)

# Run cross validation on numpy array as before
cv_scores = cross_val_score(
    cv_model,
    X_selected,
    y,
    cv=cv,
    scoring="roc_auc",
    n_jobs=-1
)

print("\nCV Scores:", cv_scores)
print("Mean:", cv_scores.mean())
print("Std :", cv_scores.std())

# ==========================================
# SPLIT
# ==========================================

# Split using DataFrame representation to preserve column names
X_train, X_test, y_train, y_test = train_test_split(
    X_selected_df,
    y,
    test_size=0.30,
    stratify=y,
    random_state=42
)

# ==========================================
# SMOTE
# ==========================================

smote = SMOTE(
    random_state=42,
    k_neighbors=3
)

X_train_resampled, y_train_resampled = smote.fit_resample(
    X_train,
    y_train
)

print(
    "After SMOTE:",
    X_train_resampled.shape
)

# ==========================================
# XGBOOST
# ==========================================

model = XGBClassifier(
    n_estimators=500,
    max_depth=5,
    learning_rate=0.03,
    subsample=0.8,
    colsample_bytree=0.8,
    scale_pos_weight=111,
    random_state=42,
    eval_metric="logloss",
    n_jobs=-1
)

model.fit(
    X_train_resampled,
    y_train_resampled
)

# ==========================================
# ISOLATION FOREST
# ==========================================

iso_model = IsolationForest(
    contamination=0.01,
    random_state=42,
    n_estimators=300
)

iso_model.fit(X_train)

print("Models Trained")
predictions = model.predict(X_test)

probabilities = model.predict_proba(
    X_test
)[:,1]

accuracy = accuracy_score(
    y_test,
    predictions
)

precision = precision_score(
    y_test,
    predictions
)

recall = recall_score(
    y_test,
    predictions
)

f1 = f1_score(
    y_test,
    predictions
)

auc = roc_auc_score(
    y_test,
    probabilities
)

print("\n===== FINAL RESULTS =====")

print("Accuracy :", accuracy)
print("Precision:", precision)
print("Recall   :", recall)
print("F1 Score :", f1)
print("ROC-AUC  :", auc)

# Isolation Forest anomaly scoring on test set
anomaly_scores = iso_model.decision_function(
    X_test
)

risk_df = pd.DataFrame({
    "Fraud_Probability": probabilities
})

risk_df["ML_Risk"] = (
    probabilities * 100
)

risk_df["Anomaly_Risk"] = (
    (
        anomaly_scores.max()
        - anomaly_scores
    )
    /
    (
        anomaly_scores.max()
        - anomaly_scores.min()
    )
) * 100

risk_df["Final_Risk_Score"] = (
    0.8 * risk_df["ML_Risk"]
    +
    0.2 * risk_df["Anomaly_Risk"]
)

# Save risk scores CSV
risk_df.to_csv(
    "fage_final_risk_scores.csv",
    index=False
)

# Save models locally
joblib.dump(
    model,
    "fage_xgboost_model.pkl"
)

joblib.dump(
    iso_model,
    "fage_isolation_forest.pkl"
)

# SHAP Analysis
explainer = shap.TreeExplainer(
    model
)

sample = X_test[:200]

shap_values = explainer.shap_values(
    sample
)

shap.summary_plot(
    shap_values,
    sample,
    show=False
)

plt.savefig(
    "shap_summary.png",
    dpi=300,
    bbox_inches="tight"
)

plt.close()

print("\nSaved Files:")
print("fage_xgboost_model.pkl")
print("fage_isolation_forest.pkl")
print("fage_final_risk_scores.csv")
print("shap_summary.png")

# ==========================================
# SAVE COMPATIBLE MODEL ARTIFACTS FOR FAGE
# ==========================================

print("\n--- Generating FAGE Dashboard Pickles ---")
models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.makedirs(models_dir, exist_ok=True)

# 1. Fit compatible FAGEPreprocessor
print("Fitting FAGEPreprocessor state...")
fage_preprocessor = FAGEPreprocessor(
    variance_threshold=0.01,
    imputation_strategy_numeric="median"
)
# We manually fit the preprocessor using the original X (which is before SelectKBest)
# so it matches FAGE's expectation
fage_preprocessor.fit(X, y)

# 2. Create compatible FAGEFeatureSelector state containing user's exact selected features
print("Fitting FAGEFeatureSelector state...")
fage_selector = FAGEFeatureSelector()
fage_selector.selected_features_ = list(final_features)
fage_selector.is_fitted_ = True

# 3. Save to models folder
with open(os.path.join(models_dir, "preprocessor.pkl"), "wb") as f:
    pickle.dump(fage_preprocessor, f)

with open(os.path.join(models_dir, "selector.pkl"), "wb") as f:
    pickle.dump(fage_selector, f)

with open(os.path.join(models_dir, "xgboost_classifier.pkl"), "wb") as f:
    pickle.dump(model, f)

with open(os.path.join(models_dir, "isolationforest_classifier.pkl"), "wb") as f:
    pickle.dump(iso_model, f)

# 4. Save metadata for inference risk calculation
anomaly_train_scores = iso_model.decision_function(X_train)
anomaly_min = float(anomaly_train_scores.min())
anomaly_max = float(anomaly_train_scores.max())

risk_metadata = {
    "anomaly_score_min": anomaly_min,
    "anomaly_score_max": anomaly_max
}

with open(os.path.join(models_dir, "risk_metadata.json"), "w") as f:
    json.dump(risk_metadata, f, indent=4)

print("Saved FAGE Dashboard models to:", models_dir)
print("Finished compiling ML pipeline successfully!")
