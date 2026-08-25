import json
import logging
import numpy as np
from sqlalchemy.orm import Session
from sklearn.metrics.pairwise import cosine_similarity
from app.db import AlertModel

logger = logging.getLogger("FAGE.SimilarityEngine")

class MuleSimilarityEngine:
    def __init__(self):
        self.is_initialized = False
        self.feature_keys = []
        self.matrix = None
        self.alert_ids = []
        self.alerts_data = []

    def initialize(self, db: Session):
        logger.info("Initializing in-memory similarity matrix for up to 1000 recent cases...")
        try:
            
            recent_alerts = db.query(AlertModel)                .filter(AlertModel.features.isnot(None))                .filter(AlertModel.status == 'confirmed')                .order_by(AlertModel.timestamp.desc())                .limit(1000)                .all()

            if not recent_alerts:
                logger.warning("No alerts found for similarity engine.")
                return

            
            for alert in recent_alerts:
                try:
                    feat_dict = json.loads(alert.features)
                    self.feature_keys = sorted([
                        k for k, v in feat_dict.items()
                        if isinstance(v, (int, float)) and not isinstance(v, bool)
                    ])
                    if self.feature_keys:
                        break
                except Exception:
                    continue

            if not self.feature_keys:
                logger.warning("Could not extract valid feature keys for similarity engine.")
                return

            matrix_rows = []
            valid_ids = []
            valid_alerts = []
            
            for alert in recent_alerts:
                try:
                    feat_dict = json.loads(alert.features)
                    
                    row = [float(feat_dict.get(k, 0.0)) for k in self.feature_keys]
                    matrix_rows.append(row)
                    valid_ids.append(alert.id)
                    
                    explain = {}
                    try:
                        explain = json.loads(alert.explainability) if alert.explainability else {}
                    except Exception:
                        pass
                    
                    valid_alerts.append({
                        "id": alert.id,
                        "riskScore": alert.risk_score,
                        "status": alert.status,
                        "timestamp": alert.timestamp,
                        "explainability": explain
                    })
                except Exception:
                    continue

            if matrix_rows:
                self.matrix = np.array(matrix_rows)
                self.alert_ids = valid_ids
                self.alerts_data = valid_alerts
                self.is_initialized = True
                logger.info(f"Similarity matrix initialized with {len(self.alert_ids)} cases and {self.matrix.shape[1]} features.")
        except Exception as e:
            logger.error(f"Failed to initialize SimilarityEngine: {e}")

    def find_similar(self, alert_features: dict, top_n: int = 5, exclude_id: str = None):
        if not self.is_initialized or self.matrix is None or len(self.alert_ids) == 0:
            return []

        
        try:
            target_vec = np.array([float(alert_features.get(k, 0.0)) for k in self.feature_keys]).reshape(1, -1)
        except Exception as e:
            logger.error(f"Failed to vectorize target for similarity: {e}")
            return []

        
        sims = cosine_similarity(target_vec, self.matrix)[0]

        
        top_indices = np.argsort(sims)[::-1]
        
        results = []
        for idx in top_indices:
            a_id = self.alert_ids[idx]
            if exclude_id and a_id == exclude_id:
                continue
                
            sim_score = float(sims[idx])
            alert_data = self.alerts_data[idx]
            
            results.append({
                "alert_id": alert_data["id"],
                "similarity_pct": round(sim_score * 100, 1),
                "risk_score": alert_data["riskScore"],
                "status": alert_data["status"],
                "timestamp": alert_data["timestamp"],
                "top_shap_drivers": [d.get("feature") for d in alert_data["explainability"].get("key_risk_drivers", [])[:2]]
            })
            
            if len(results) >= top_n:
                break
                
        return results

similarity_engine = MuleSimilarityEngine()
