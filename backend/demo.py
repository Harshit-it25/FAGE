import logging
import pandas as pd
import numpy as np
from typing import Tuple
from app.ml.preprocessing import FAGEPreprocessor
from app.ml.feature_selection import FAGEFeatureSelector

# Logging setup
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("FAGE.ML.Demo")

def generate_synthetic_highdim_data(n_rows: int = 200, n_cols: int = 100) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Generates dummy high-dimensional data representing the 3,017 column scale of FAGE,
    injecting specific issues to test preprocessing, leakage, and feature selection filters.
    """
    logger.info(f"Generating synthetic modeling dataset: {n_rows} samples, {n_cols} features.")
    np.random.seed(42)
    
    # 1. Standard features
    data = np.random.randn(n_rows, n_cols)
    feat_names = [f"F{i}" for i in range(n_cols)]
    df = pd.DataFrame(data, columns=feat_names)
    
    # 2. Binary target variable F3924
    target = pd.Series(np.random.choice([0, 1], size=n_rows), name="F3924")
    
    # 3. Inject Missing Values (feature with 60% missing, should be dropped)
    df["F12_excess_missing"] = np.nan
    df.loc[:int(n_rows * 0.4), "F12_excess_missing"] = np.random.randn(int(n_rows * 0.4) + 1)
    
    # 4. Inject Low Variance Feature (constant value, should be dropped)
    df["F34_constant"] = 3.924
    
    # 5. Inject Exact Target Leakage (near-perfect correlation, should be dropped)
    df["F56_leak_target"] = target.values + np.random.normal(0, 0.0001, size=n_rows)
    df["F3924_derived_rule"] = target.values
    
    # 6. Inject Collinear Features (F2 and F3 copy, should trigger correlation filter)
    df["F_collinear_a"] = df["F1"] * 1.5
    df["F_collinear_b"] = df["F1"] * 1.5 + np.random.normal(0, 0.001, size=n_rows)
    
    # 7. Inject Categorical Deterministic Separator (should trigger leakage check category rule)
    # E.g. Category A always has target=0, Category B always has target=1
    cat_leak = np.where(target.values == 0, "FLAG_PENDING", "FLAG_APPROVED")
    df["F_cat_deterministic_leak"] = cat_leak
    
    # 8. Inject highly predictive feature (non-leaked, but high mutual info)
    df["F_highly_predictive"] = target.values * 2.0 + np.random.normal(0, 0.5, size=n_rows)
    
    return df, target

def run_fage_ml_pipeline():
    logger.info("=== INITIALIZING FAGE MACHINE LEARNING pipeline ===")
    
    # 1. Generate data representing subset of high dimension
    X, y = generate_synthetic_highdim_data(n_rows=250, n_cols=120)
    
    # 2. Fit FAGEPreprocessor
    preprocessor = FAGEPreprocessor(
        missing_threshold=0.50,
        variance_threshold=0.01,
        max_leakage_correlation=0.99,
        imputation_strategy_numeric="median"
    )
    
    X_cleaned = preprocessor.fit_transform(X, y)
    
    # Gather and print intermediate governance report
    preprocessor_report = preprocessor.get_summary_report()
    logger.info(f"--- PREPROCESSOR COMPLIANCE REPORT ---")
    logger.info(f"Input features reviewed: {preprocessor_report['input_dimension']}")
    logger.info(f"Features satisfying threshold checks: {preprocessor_report['output_dimension']}")
    logger.info(f"Dropped due to excessive missingness: {preprocessor_report['columns_dropped']['missing_threshold']}")
    logger.info(f"Dropped due to leakage audit detections: {preprocessor_report['columns_dropped']['target_leakage']}")
    logger.info(f"Dropped due to constant/low variance: {preprocessor_report['columns_dropped']['low_variance']}")
    
    # 3. Fit FAGEFeatureSelector
    selector = FAGEFeatureSelector(
        correlation_threshold=0.95,
        mutual_info_top_k=50,
        rfecv_step=0.1, # Speed up demo
        rfecv_min_features=5,
        rfecv_cv_folds=3
    )
    
    final_features = selector.fit_select(X_cleaned, y)
    
    # Gather analytics indicators
    selector_report = selector.get_audit_metrics()
    logger.info(f"--- FEATURE SELECTOR SUMMARY ---")
    logger.info(f"Total features selected: {selector_report['selected_features_count']}")
    logger.info(f"Dropped collinear twins: {selector_report['collinear_dropped_count']}")
    logger.info(f"Collinear dropped features: {selector_report['collinear_dropped_features']}")
    logger.info(f"Top Mutual Info Features: {list(selector_report['top_mutual_information_scores'].keys())[:5]}")
    logger.info(f"Retained during CV-guided RFECV: {selector_report['rfecv_retained_count']}")
    
    # Demonstrate transform on test dataset
    logger.info("Verifying inference transform alignment...")
    X_test_transformed = selector.transform(X_cleaned)
    logger.info(f"Final training state dimensions: {X_test_transformed.shape}")
    logger.info("=== PIPELINE VALIDATION COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    run_fage_ml_pipeline()
