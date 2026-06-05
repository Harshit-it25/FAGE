import sys
import os
import logging
from typing import Dict, List, Tuple, Any, Optional, Union
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

# Set up logging for FAGE Machine Learning Pipeline
logger = logging.getLogger("FAGE.ML.Preprocessing")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class FAGEPreprocessor(BaseEstimator, TransformerMixin):
    """
    Production-grade preprocessing engine for FAGE (Fraud Analytics & Governance Engine).
    Designed to handle high-dimensional fraudulent transaction datasets (e.g., 3,017 columns, 7,777 rows).
    
    This preprocessor carries out:
    1. Missing value analysis and filtering.
    2. Variance thresholding to remove near-constant features.
    3. Strict target leakage validation (checks proxies, high correlations, target name overlap).
    4. Enterprise imputation (using fitted statistics) to prevent training-serving skew.
    """

    def __init__(
        self,
        missing_threshold: float = 0.50,
        variance_threshold: float = 0.01,
        max_leakage_correlation: float = 0.999,
        imputation_strategy_numeric: str = "median",
        imputation_strategy_categorical: str = "most_frequent",
    ):
        """
        Initializes the FAGEPreprocessor with configurable structural thresholds.
        
        Args:
            missing_threshold: Maximum fraction of missing values allowed for a feature.
            variance_threshold: Variance cutoff for near-constant features.
            max_leakage_correlation: Maximum allowed absolute correlation with target before flagged as leakage.
            imputation_strategy_numeric: Method for numeric imputation ('mean' or 'median').
            imputation_strategy_categorical: Method for categorical imputation ('most_frequent' or 'constant_missing').
        """
        self.missing_threshold = missing_threshold
        self.variance_threshold = variance_threshold
        self.max_leakage_correlation = max_leakage_correlation
        self.imputation_strategy_numeric = imputation_strategy_numeric
        self.imputation_strategy_categorical = imputation_strategy_categorical

        # Fitted parameters (State Tracker for Production serving)
        self.input_columns_: List[str] = []
        self.output_columns_: List[str] = []
        self.numeric_features_: List[str] = []
        self.categorical_features_: List[str] = []
        
        # Drop logs for governance audit trails
        self.dropped_missing_cols_: List[str] = []
        self.dropped_low_variance_cols_: List[str] = []
        self.dropped_leakage_cols_: List[str] = []
        
        # Imputation states
        self.impute_values_: Dict[str, Any] = {}
        self.is_fitted_ = False

    def analyze_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Analyzes missing value distributions and counts, logging statistical profiles.
        
        Args:
            df: Input pandas DataFrame to analyze.
            
        Returns:
            A summary DataFrame containing missing count, percentage, and dtype per column.
        """
        missing_counts = df.isnull().sum()
        missing_pct = df.isnull().mean()
        
        summary_df = pd.DataFrame({
            "column": df.columns,
            "missing_count": missing_counts,
            "missing_percentage": missing_pct,
            "dtype": df.dtypes
        }).sort_values(by="missing_percentage", ascending=False)
        
        high_missing_count = sum(missing_pct > self.missing_threshold)
        logger.info(
            f"Missing Value Analysis: Found {high_missing_count} columns out of {df.shape[1]} "
            f"exceeding the missingness threshold of {self.missing_threshold:.1%}"
        )
        return summary_df

    def validate_and_filter_leakage(
        self, df: pd.DataFrame, target_col: str
    ) -> Tuple[List[str], Dict[str, Any]]:
        """
        Performs robust governance audits on input data to protect against target leakage.
        Checks for:
        1. Exact identifier duplicate columns.
        2. Names matching variants of target or metadata keywords (e.g. '_target', 'F3924_derived').
        3. Features with an absolute correlation exceeding max_leakage_correlation with the target.
        4. Columns that acts as a deterministic separator.
        
        Args:
            df: Input DataFrame containing features and target.
            target_col: Target column name (e.g. 'F3924').
            
        Returns:
            A tuple of:
            - List of columns flagged as target leakage to drop.
            - A dictionary summarizing the specific validation results for audit compliance.
        """
        logger.info(f"Target Leakage Audit initiated against target: {target_col}")
        leakage_cols = []
        audit_report: Dict[str, Any] = {
            "target": target_col,
            "high_correlation_rules": [],
            "name_overlap_rules": [],
            "deterministic_separators": []
        }

        if target_col not in df.columns:
            logger.warning(f"Target column '{target_col}' not found in DataFrame. Skipping leakage validation.")
            return leakage_cols, audit_report

        y = df[target_col].copy()
        
        # 1. Check for exact duplicate target column or name variations
        normalized_target = target_col.lower().strip()
        for col in df.columns:
            if col == target_col:
                continue
                
            col_lower = col.lower().strip()
            # Flag if the column name looks suspiciously like derivative metadata of the target
            if (normalized_target in col_lower and 
                any(suffix in col_lower for suffix in ["leak", "target", "label", "derived", "output", "y"])):
                leakage_cols.append(col)
                audit_report["name_overlap_rules"].append({
                    "column": col,
                    "reason": f"Name similarity indicating target derivation: '{col}' contains '{target_col}'"
                })

        # 2. Check for extreme correlations
        # We process numeric columns for correlation limit checks
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if target_col in numeric_cols:
            # Drop target from numeric list to avoid self-correlation
            corr_numeric = [c for c in numeric_cols if c != target_col]
            
            # Compute correlation with target
            corr_scores = df[corr_numeric].corrwith(y).abs()
            high_corr_features = corr_scores[corr_scores >= self.max_leakage_correlation].index.tolist()
            
            for col in high_corr_features:
                if col not in leakage_cols:
                    leakage_cols.append(col)
                audit_report["high_correlation_rules"].append({
                    "column": col,
                    "correlation": float(corr_scores[col]),
                    "reason": f"Absolute correlation score of {corr_scores[col]:.5f} is >= threshold {self.max_leakage_correlation}"
                })

        # 3. Check for deterministic categorical separators (e.g., status flags generated post-facto)
        categorical_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()
        categorical_cols = [c for c in categorical_cols if c != target_col]
        
        for col in categorical_cols:
            # If for each category value, target is perfectly deterministic:
            crosstab = pd.crosstab(df[col], y)
            # If all rows of the crosstab have only 1 non-zero value, it means the column perfectly partitions the target
            if crosstab.apply(lambda row: (row > 0).sum() <= 1, axis=1).all() and len(crosstab) > 1:
                if col not in leakage_cols:
                    leakage_cols.append(col)
                audit_report["deterministic_separators"].append({
                    "column": col,
                    "reason": "Perfect partition. Category values perfectly separate target state (post-facto metadata leak risk)."
                })

        logger.info(f"Leakage validation audited. Flagged {len(leakage_cols)} columns as potential leakage.")
        return leakage_cols, audit_report

    def fit(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> "FAGEPreprocessor":
        """
        Computes all preprocessing parameters, identifying missing features, low-variance bounds, 
        and training stat summaries for imputation.
        
        Args:
            X: Input DataFrame of features.
            y: Opional Target pandas Series (F3924), utilized for target leakage checks.
            
        Returns:
            Fitted preprocessor instance.
        """
        logger.info(f"Fitting preprocessor on dataset of shape {X.shape}")
        self.input_columns_ = X.columns.tolist()
        
        # Reset fitted states
        self.dropped_missing_cols_ = []
        self.dropped_low_variance_cols_ = []
        self.dropped_leakage_cols_ = []
        self.impute_values_ = {}

        # 1. Deep Missing Value Analysis
        missing_summary = self.analyze_missing_values(X)
        self.dropped_missing_cols_ = missing_summary[
            missing_summary["missing_percentage"] > self.missing_threshold
        ]["column"].tolist()
        
        if self.dropped_missing_cols_:
            logger.info(f"Filtering {len(self.dropped_missing_cols_)} columns with excessive missingness (> {self.missing_threshold:.0%})")

        # Column set remaining after missingness filtering
        active_cols = [c for c in self.input_columns_ if c not in self.dropped_missing_cols_]
        
        # 2. Target Leakage Validation (if target Series is supplied)
        target_name = y.name if (y is not None and y.name) else "F3924"
        if y is not None:
            # Reconstruct unified subframe to inspect targets safely
            sub_df = X[active_cols].copy()
            sub_df[target_name] = y
            self.dropped_leakage_cols_, _ = self.validate_and_filter_leakage(sub_df, target_col=target_name)
            
            # Exclude the target name if it was somehow appended
            self.dropped_leakage_cols_ = [c for c in self.dropped_leakage_cols_ if c != target_name]
            active_cols = [c for c in active_cols if c not in self.dropped_leakage_cols_]

        # 3. Variance Threshold Selection
        # Separate numeric columns among current active columns
        numeric_active = X[active_cols].select_dtypes(include=[np.number]).columns.tolist()
        categorical_active = X[active_cols].select_dtypes(exclude=[np.number]).columns.tolist()

        for col in numeric_active:
            col_var = X[col].var(ddof=0)
            if pd.isna(col_var) or col_var <= self.variance_threshold:
                self.dropped_low_variance_cols_.append(col)
                
        # Drop constant categoricals (1 unique category value)
        for col in categorical_active:
            if X[col].nunique(dropna=True) <= 1:
                self.dropped_low_variance_cols_.append(col)

        if self.dropped_low_variance_cols_:
            logger.info(f"Filtering {len(self.dropped_low_variance_cols_)} low-variance/constant columns (<= {self.variance_threshold})")

        # Refine final active columns list
        self.output_columns_ = [
            c for c in active_cols if c not in self.dropped_low_variance_cols_
        ]

        # 4. Fitted Imputation Map Preparation
        # Restrict modeling targets specifically to output columns
        self.numeric_features_ = X[self.output_columns_].select_dtypes(include=[np.number]).columns.tolist()
        self.categorical_features_ = X[self.output_columns_].select_dtypes(exclude=[np.number]).columns.tolist()

        # Compute imputation values for numerics
        for col in self.numeric_features_:
            if self.imputation_strategy_numeric == "median":
                self.impute_values_[col] = X[col].median(skipna=True)
            else:
                self.impute_values_[col] = X[col].mean(skipna=True)
            
            # Fallback if whole column is null (which shouldn't happen after missingness filter)
            if pd.isna(self.impute_values_[col]):
                self.impute_values_[col] = 0.0

        # Compute imputation values for categoricals
        for col in self.categorical_features_:
            if self.imputation_strategy_categorical == "most_frequent":
                mode_series = X[col].mode(dropna=True)
                self.impute_values_[col] = mode_series.iloc[0] if not mode_series.empty else "UNKNOWN"
            else:
                self.impute_values_[col] = "UNKNOWN"

        self.is_fitted_ = True
        logger.info(
            f"FAGEPreprocessor fit complete! Input columns: {len(self.input_columns_)} | "
            f"Dropped missing: {len(self.dropped_missing_cols_)} | "
            f"Dropped leakage: {len(self.dropped_leakage_cols_)} | "
            f"Dropped low var: {len(self.dropped_low_variance_cols_)} | "
            f"Remaining Features: {len(self.output_columns_)}"
        )
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Transforms input DataFrame utilizing parameters locked during fit phase.
        Ensures consistent feature lists and imputes any remaining missing cells.
        
        Args:
            X: Input DataFrame to clean.
            
        Returns:
            Transformed DataFrame containing only finalized features with zero missing values.
        """
        if not self.is_fitted_:
            raise ValueError("FAGEPreprocessor must be fitted before transform can be invoked.")
            
        logger.info(f"Transforming dataset of shape {X.shape}")
        
        # Verify alignment with expected columns or warning if inference data contains differences
        missing_input_cols = set(self.output_columns_) - set(X.columns)
        if missing_input_cols:
            logger.warning(
                f"Prediction dataset is missing {len(missing_input_cols)} columns expected "
                f"by preprocessor. Appending missing columns with default/imputed states."
            )
            
        # Extract of remaining columns
        transformed_df = pd.DataFrame(index=X.index)
        
        for col in self.output_columns_:
            if col in X.columns:
                series = X[col].copy()
            else:
                # Fill missing schema columns filled using static precomputed defaults
                series = pd.Series(np.nan, index=X.index, name=col)

            # Apply Imputers
            val_to_fill = self.impute_values_.get(col, 0.0 if col in self.numeric_features_ else "UNKNOWN")
            
            # Cast categorical columns to string explicitly during fill to avoid object/str mismatches
            if col in self.categorical_features_:
                series = series.astype(str).replace({"nan": np.nan, "None": np.nan})
                
            transformed_df[col] = series.fillna(val_to_fill)

        # Enforce exact type safety conversions
        for col in self.numeric_features_:
            transformed_df[col] = pd.to_numeric(transformed_df[col], errors="coerce").fillna(self.impute_values_[col])
            
        logger.info(f"Transformer process finished. Output dataframe dimensions: {transformed_df.shape}")
        return transformed_df

    def get_summary_report(self) -> Dict[str, Any]:
        """
        Generates structured audit metrics summarizing pipeline reductions and dropped column registers.
        
        Returns:
            Dictionary containing processing metadata and features catalog.
        """
        return {
            "is_fitted": self.is_fitted_,
            "input_dimension": len(self.input_columns_),
            "output_dimension": len(self.output_columns_),
            "reductions": {
                "high_missingness_dropped_count": len(self.dropped_missing_cols_),
                "target_leakage_dropped_count": len(self.dropped_leakage_cols_),
                "low_variance_dropped_count": len(self.dropped_low_variance_cols_),
            },
            "columns_dropped": {
                "missing_threshold": self.dropped_missing_cols_,
                "target_leakage": self.dropped_leakage_cols_,
                "low_variance": self.dropped_low_variance_cols_
            },
            "features_signature": {
                "numeric_features_count": len(self.numeric_features_),
                "categorical_features_count": len(self.categorical_features_)
            }
        }
