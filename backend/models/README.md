# Placeholder — trained model pickles will be written here by train_models.py

## xgb_recall_optimized_model.pkl

Added as part of the audit fixes (see /FAGE_bug_audit_and_retrain.md at repo root). Trained
outside the main train_models.py pipeline via retrain_fixed.py + recall_experiments.py, on the
full DataSet.csv, with all leak fixes applied (see below) and a 1200-feature budget instead of
450. Contains a dict: {"model": XGBClassifier, "features": [...], "threshold": 0.4}.

Pooled 15-fold CV: precision 0.887 ± 0.072, recall 0.838 ± 0.089, F1 0.857 ± 0.054.

This is a validated candidate, NOT yet wired into `risk_engine` / `inference.py`. Before using
it in the API, swap it in for `xgboost_classifier.pkl` and confirm `app/ml` inference code
loads the dict structure correctly (current inference code expects a bare classifier for some
paths — check `app/main.py` / `RiskEngine` model-loading logic before deploying).
