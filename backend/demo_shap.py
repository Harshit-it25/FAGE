import sys
import os
import json
import logging
import pandas as pd
import numpy as np
from typing import Tuple

# Adjust module search path for execution
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.ml.preprocessing import FAGEPreprocessor
from app.ml.feature_selection import FAGEFeatureSelector
from app.ml.shap_engine import FAGEShapEngine

from sklearn.ensemble import RandomForestClassifier

# Logging Setup
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("FAGE.ML.ShapDemo")


def generate_synthetic_data(n_rows: int = 150, n_cols: int = 50) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Generates synthetic modeling datasets to demonstrate explainability algorithms.
    """
    logger.info(f"Generating synthetic demonstration data: {n_rows} rows x {n_cols} columns")
    np.random.seed(42)
    
    data = np.random.randn(n_rows, n_cols)
    cols = [f"F_METRIC_{i}" for i in range(n_cols)]
    df = pd.DataFrame(data, columns=cols)
    
    # Highly imbalanced fraudulent flag
    y = pd.Series(np.random.choice([0, 1], size=n_rows, p=[0.90, 0.10]), name="F3924")
    
    # Inject extremely strong predictive triggers to explain
    df["F_METRIC_0"] = y.values * 3.5 + np.random.normal(0, 0.5, size=n_rows) # Highly positive
    df["F_METRIC_1"] = y.values * (-2.8) + np.random.normal(0, 0.5, size=n_rows) # Highly negative
    
    return df, y


def test_shap_engine_pipeline():
    logger.info("=== STARTING SHAP EXPLAINABILITY ENGINE VERIFICATION ===")
    
    # 1. Generate core datasets
    X, y = generate_synthetic_data(n_rows=200, n_cols=60)
    
    # 2. Fit and transform pipeline wrappers
    preprocessor = FAGEPreprocessor(missing_threshold=0.50, variance_threshold=0.01)
    X_pro = preprocessor.fit_transform(X, y)
    
    selector = FAGEFeatureSelector(correlation_threshold=0.95, mutual_info_top_k=25, rfecv_step=0.2, rfecv_min_features=5)
    selected_cols = selector.fit_select(X_pro, y)
    X_sel = selector.transform(X_pro)
    
    # 3. Train target classifier representing audit frameworks
    logger.info("Fitting Random Forest classifier on clean selected dataset...")
    rf_clf = RandomForestClassifier(n_estimators=30, max_depth=5, random_state=42)
    rf_clf.fit(X_sel, y)
    
    # 4. Initialize FAGEShapEngine
    logger.info("Initializing FAGEShapEngine on validation background states...")
    shap_engine = FAGEShapEngine(
        model=rf_clf,
        background_data=X_sel,
        model_name="RandomForestClassifier"
    )
    
    # Test Global SHAP summary
    logger.info("Computing Global mean absolute SHAP importances...")
    global_rankings = shap_engine.compute_global_shap(X_sel)
    logger.info("Global Rank Score Summary Table:")
    for feat, score in list(global_rankings.items())[:5]:
        logger.info(f" - {feat}: {score:.5f}")
        
    # Extract mock fraudulent row index to explain
    high_risk_indices = y[y == 1].index.tolist()
    if high_risk_indices:
        test_index = high_risk_indices[0]
        logger.info(f"Targeting active fraudulent case at index [{test_index}] to generate Local Explanations...")
    else:
        test_index = 0
        logger.info(f"No positive label found. Selecting baseline case index [{test_index}] to explain...")
        
    audit_row = X_sel.iloc[test_index]
    
    # Test Local Explainer Coordinate Output
    local_vals = shap_engine.compute_local_shap(audit_row)
    logger.info("Raw local attribution values computed successfully.")
    
    # Test Waterfall visual mapping data
    logger.info("Generating fully formatted Waterfall components mapping payload...")
    waterfall_payload = shap_engine.generate_waterfall_data(audit_row)
    logger.info(f"Waterfall step list size: {len(waterfall_payload['steps'])}")
    logger.info(f"Step 0 (Base Expectation): {waterfall_payload['steps'][0]['cumulative']:.4%}")
    logger.info(f"Final Value Prediction: {waterfall_payload['final_value']:.4%}")
    
    # Test Summary scatter visual coordinates
    logger.info("Generating Summary scatter beeswarm coordinates...")
    summary_coords = shap_engine.generate_summary_data(X_sel)
    logger.info(f"Selected Summary features list: {summary_coords['top_features']}")
    logger.info(f"Generated scatter points coordinates count: {len(summary_coords['points'])}")
    
    # Test Base64 static rendering
    logger.info("Testing Base64 static graph compiler rendering engines...")
    waterfall_b64 = shap_engine.render_base64_waterfall(audit_row)
    summary_b64 = shap_engine.render_base64_summary(X_sel)
    
    logger.info(f"Waterfall Base64 length: {len(waterfall_b64) if waterfall_b64 else 0} bytes")
    logger.info(f"Summary Base64 length: {len(summary_b64) if summary_b64 else 0} bytes")
    
    logger.info("=== SHAP VEHICLE MODULE COMPILATION AND VERIFICATION COMPLETED ===")


if __name__ == "__main__":
    test_shap_engine_pipeline()
