import sys
import os
import logging
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin


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
    4. Robust imputation (using fitted statistics) to prevent training-serving skew.
    """

    def __init__(
        self,
        missing_threshold: float = 0.50,
        variance_threshold: float = 0.01,
        max_leakage_correlation: float = 0.999,
        imputation_strategy_numeric: str = "median",
        imputation_strategy_categorical: str = "most_frequent",
        protected_features: Optional[List[str]] = None,
    ):
        """
        Initializes the FAGEPreprocessor with configurable structural thresholds.
        
        Args:
            missing_threshold: Maximum fraction of missing values allowed for a feature.
            variance_threshold: Variance cutoff for near-constant features.
            max_leakage_correlation: Maximum allowed absolute correlation with target before flagged as leakage.
            imputation_strategy_numeric: Method for numeric imputation ('mean' or 'median').
            imputation_strategy_categorical: Method for categorical imputation ('most_frequent' or 'constant_missing').
            protected_features: Column names (e.g. organizer-mandated features) that must never be
                dropped by the missingness or variance filters. They can still be dropped by the
                target-leakage check, since a genuine leak is a correctness issue, not a policy one.
        """
        self.missing_threshold = missing_threshold
        self.variance_threshold = variance_threshold
        self.max_leakage_correlation = max_leakage_correlation
        self.imputation_strategy_numeric = imputation_strategy_numeric
        self.imputation_strategy_categorical = imputation_strategy_categorical
        self.protected_features = set(protected_features or [])

        
        self.input_columns_: List[str] = []
        self.output_columns_: List[str] = []
        self.numeric_features_: List[str] = []
        self.categorical_features_: List[str] = []
        
        
        
        self.date_features_: List[str] = []
        self.date_reference_: Dict[str, Dict[str, float]] = {}
        
        
        self.dropped_missing_cols_: List[str] = []
        self.dropped_low_variance_cols_: List[str] = []
        self.dropped_leakage_cols_: List[str] = []
        
        
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

        
        
        # FIXED (audit finding, see FAGE_bug_audit_and_retrain.md #1):
        # This list previously included F3887 and F3894, which are organizer-MANDATED seed
        # features (HIGHLIGHTED_FEATURES in train_models.py). They were being force-dropped as
        # "leaks" purely because their column numbers fell in this numeric range, with NO
        # correlation check behind it. Verified against the actual dataset:
        #   F3887: corr=+0.004, univariate AUROC=0.524 -> noise, not a leak
        #   F3894: corr=-0.008, univariate AUROC=0.553 -> noise, not a leak
        # F3898 (MIN_RESOLVE_DAYS) was also previously in this list. The competitor's own
        # published leak audit explicitly RETAINED it after finding an ablation showed -27pp
        # precision if removed, and it is the #1 SHAP driver in their model. Dropping it here
        # unconditionally silently threw away a genuinely predictive, non-leaky feature.
        # Only the columns independently confirmed as post-event resolution/alert-outcome flags
        # remain in this list (F3908, F3912-F3914 confirmed via correlation/AUROC scan; the
        # F3899-F3907/F3909-F3911/F3915/F3919-F3923 block is the surrounding alert/resolution
        # metadata family these belong to and was not individually re-verified here -- if you
        # add any of them back, re-run the correlation/AUROC check in retrain_fixed.py first).
        semantic_leakage_features = [
            'F3899', 'F3900', 'F3901', 'F3902', 'F3903',
            'F3904', 'F3905', 'F3906', 'F3907', 'F3908', 'F3909', 'F3910', 'F3911',
            'F3912', 'F3913', 'F3914', 'F3915', 'F3919', 'F3920', 'F3921', 'F3922', 'F3923'
        ]
        
        found_semantic = [f for f in semantic_leakage_features if f in df.columns]
        # Protected features (organizer-mandated seed columns) are never force-dropped by this
        # rule, even if a future edit re-adds their column number to the range above.
        found_semantic = [f for f in found_semantic if f not in self.protected_features]
        if found_semantic:
            logger.warning(f"Found {len(found_semantic)} confirmed semantic leakage features. Force dropping.")
            leakage_cols.extend(found_semantic)
            audit_report["semantic_leakage"] = found_semantic

        if target_col not in df.columns:
            logger.warning(f"Target column '{target_col}' not found in DataFrame. Skipping statistical leakage validation.")
            return leakage_cols, audit_report

        y = df[target_col].copy()
        
        
        normalized_target = target_col.lower().strip()
        for col in df.columns:
            if col == target_col:
                continue
                
            col_lower = col.lower().strip()
            
            if (normalized_target in col_lower and 
                any(suffix in col_lower for suffix in ["leak", "target", "label", "derived", "output", "y"])):
                leakage_cols.append(col)
                audit_report["name_overlap_rules"].append({
                    "column": col,
                    "reason": f"Name similarity indicating target derivation: '{col}' contains '{target_col}'"
                })

        
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if target_col in numeric_cols:
            
            corr_numeric = [c for c in numeric_cols if c != target_col]
            
            
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

        
        categorical_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()
        categorical_cols = [c for c in categorical_cols if c != target_col]
        
        for col in categorical_cols:
            
            crosstab = pd.crosstab(df[col], y)
            
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
        
        
        self.dropped_missing_cols_ = []
        self.dropped_low_variance_cols_ = []
        self.dropped_leakage_cols_ = []
        self.impute_values_ = {}

        
        missing_summary = self.analyze_missing_values(X)
        self.dropped_missing_cols_ = missing_summary[
            missing_summary["missing_percentage"] > self.missing_threshold
        ]["column"].tolist()

        
        
        
        rescued_missing = [c for c in self.dropped_missing_cols_ if c in self.protected_features]
        if rescued_missing:
            logger.info(f"Protected features exempted from missingness filter: {rescued_missing}")
            self.dropped_missing_cols_ = [c for c in self.dropped_missing_cols_ if c not in self.protected_features]

        if self.dropped_missing_cols_:
            logger.info(f"Filtering {len(self.dropped_missing_cols_)} columns with excessive missingness (> {self.missing_threshold:.0%})")

        
        active_cols = [c for c in self.input_columns_ if c not in self.dropped_missing_cols_]
        
        
        target_name = y.name if (y is not None and y.name) else "F3924"
        if y is not None:
            
            sub_df = X[active_cols].copy()
            sub_df[target_name] = y
            self.dropped_leakage_cols_, _ = self.validate_and_filter_leakage(sub_df, target_col=target_name)
            
            
            self.dropped_leakage_cols_ = [c for c in self.dropped_leakage_cols_ if c != target_name]
            active_cols = [c for c in active_cols if c not in self.dropped_leakage_cols_]

        
        
        numeric_active = X[active_cols].select_dtypes(include=[np.number]).columns.tolist()
        categorical_active = X[active_cols].select_dtypes(exclude=[np.number]).columns.tolist()

        for col in numeric_active:
            
            
            
            
            
            
            
            
            p05, p95 = X[col].quantile(0.05), X[col].quantile(0.95)
            col_range = p95 - p05
            if col_range == 0 or pd.isna(col_range):
                normalized_var = 0.0
            else:
                normalized_var = (((X[col] - p05) / col_range).clip(-5, 5)).var(ddof=0)

            if pd.isna(normalized_var) or normalized_var <= self.variance_threshold:
                self.dropped_low_variance_cols_.append(col)
                
        
        for col in categorical_active:
            if X[col].nunique(dropna=True) <= 1:
                self.dropped_low_variance_cols_.append(col)

        
        rescued_variance = [c for c in self.dropped_low_variance_cols_ if c in self.protected_features]
        if rescued_variance:
            logger.info(f"Protected features exempted from variance filter: {rescued_variance}")
            self.dropped_low_variance_cols_ = [c for c in self.dropped_low_variance_cols_ if c not in self.protected_features]

        if self.dropped_low_variance_cols_:
            logger.info(f"Filtering {len(self.dropped_low_variance_cols_)} low-variance/constant columns (<= {self.variance_threshold})")

        
        self.output_columns_ = [
            c for c in active_cols if c not in self.dropped_low_variance_cols_
        ]

        
        
        
        
        
        
        
        candidate_cols = X[self.output_columns_].select_dtypes(exclude=[np.number]).columns.tolist()
        self.date_features_ = []
        self.date_reference_ = {}
        for col in candidate_cols:
            non_null = X[col].notna()
            if non_null.sum() == 0:
                continue
            
            
            
            
            
            
            
            if X[col].nunique(dropna=True) < 20:
                continue
            parsed = pd.to_datetime(X[col], errors="coerce", format="mixed")
            parse_rate = parsed[non_null].notna().mean()
            if parse_rate < 0.95:
                continue  

            ordinal = parsed.dropna().map(lambda d: d.toordinal())
            if len(ordinal) < 5:
                continue

            
            
            
            q1, q3 = ordinal.quantile(0.25), ordinal.quantile(0.75)
            iqr = q3 - q1
            lower_bound = (q1 - 3 * iqr) if iqr > 0 else ordinal.min()
            clean_ordinal = ordinal[ordinal >= lower_bound]
            if len(clean_ordinal) == 0:
                continue

            ref_min = float(clean_ordinal.min())
            impute_offset_days = float((clean_ordinal - ref_min).median())

            self.date_features_.append(col)
            self.date_reference_[col] = {
                "ref_ordinal_min": ref_min,
                "sentinel_lower_bound_ordinal": float(lower_bound),
                "impute_offset_days": impute_offset_days,
            }

        if self.date_features_:
            logger.info(f"Detected {len(self.date_features_)} date-valued column(s), converting to numeric recency features instead of string categories: {self.date_features_}")

        
        
        
        self.numeric_features_ = [
            c for c in X[self.output_columns_].select_dtypes(include=[np.number]).columns.tolist()
            if c not in self.date_features_
        ]
        self.categorical_features_ = [
            c for c in X[self.output_columns_].select_dtypes(exclude=[np.number]).columns.tolist()
            if c not in self.date_features_
        ]

        
        for col in self.numeric_features_:
            if self.imputation_strategy_numeric == "median":
                self.impute_values_[col] = X[col].median(skipna=True)
            else:
                self.impute_values_[col] = X[col].mean(skipna=True)
            
            
            if pd.isna(self.impute_values_[col]):
                self.impute_values_[col] = 0.0

        
        for col in self.categorical_features_:
            if self.imputation_strategy_categorical == "most_frequent":
                mode_series = X[col].mode(dropna=True)
                self.impute_values_[col] = mode_series.iloc[0] if not mode_series.empty else "UNKNOWN"
            else:
                self.impute_values_[col] = "UNKNOWN"

        
        
        
        self.category_maps_: Dict[str, Dict[str, int]] = {}
        for col in self.categorical_features_:
            series = X[col].astype(str).replace({"nan": np.nan, "None": np.nan})
            series = series.fillna(str(self.impute_values_[col]))
            uniques = sorted(series.unique().tolist())
            self.category_maps_[col] = {val: idx for idx, val in enumerate(uniques)}

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
        
        
        missing_input_cols = set(self.output_columns_) - set(X.columns)
        if missing_input_cols:
            logger.warning(
                f"Prediction dataset is missing {len(missing_input_cols)} columns expected "
                f"by preprocessor. Appending missing columns with default/imputed states."
            )
            
        
        cols_dict = {}
        
        for col in self.output_columns_:
            if col in X.columns:
                series = X[col].copy()
            else:
                
                series = pd.Series(np.nan, index=X.index, name=col)

            
            val_to_fill = self.impute_values_.get(col, 0.0 if col in self.numeric_features_ else "UNKNOWN")
            
            
            if col in self.categorical_features_:
                series = series.astype(str).replace({"nan": np.nan, "None": np.nan})
                
            cols_dict[col] = series.fillna(val_to_fill)

        
        for col in self.numeric_features_:
            if col in cols_dict:
                cols_dict[col] = pd.to_numeric(cols_dict[col], errors="coerce").fillna(self.impute_values_[col])

        
        for col in self.categorical_features_:
            if col in cols_dict:
                mapping = self.category_maps_.get(col, {})
                cols_dict[col] = cols_dict[col].map(mapping).fillna(-1).astype(int)

        
        for col in self.date_features_:
            if col in cols_dict:
                ref = self.date_reference_[col]
                raw_series = X[col] if col in X.columns else pd.Series(np.nan, index=X.index)
                parsed = pd.to_datetime(raw_series, errors="coerce", format="mixed")
                offset_days = parsed.map(
                    lambda d: (d.toordinal() - ref["ref_ordinal_min"]) if pd.notna(d) else np.nan
                )
                offset_days = offset_days.where(
                    (offset_days.isna()) | (offset_days >= (ref["sentinel_lower_bound_ordinal"] - ref["ref_ordinal_min"])),
                    np.nan
                )
                cols_dict[col] = offset_days.fillna(ref["impute_offset_days"]).astype(float)

        transformed_df = pd.DataFrame(cols_dict, index=X.index)
        logger.info(f"Transformer process finished. Output dataframe dimensions: {transformed_df.shape}")
        return transformed_df


