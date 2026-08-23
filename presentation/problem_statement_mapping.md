# Problem Statement to FAGE Mapping (Cheat Sheet)

When the judges ask, *"Did you actually solve the problem we gave you?"*, you will use this cheat sheet. It maps the exact wording of the hackathon problem statement directly to the features we built into FAGE.

---

### 1. "Develop an AI/ML-powered classification system capable of identifying suspicious and mule accounts"
**How FAGE solves this:**
- FAGE uses an **XGBoost classification model** wrapped in a PU (Positive-Unlabeled) learning framework.
- We don't just classify individual transactions; our engine classifies the *accounts* themselves by generating risk scores based on velocity and behavioral thresholds.

### 2. "Analyzing features from financial transaction data provided in this portal"
**How FAGE solves this:**
- We built a rigorous **Feature Engineering pipeline** (`feature_selection.py` & `preprocessing.py`). 
- We extracted velocity metrics (e.g., `velocity_6h`), behavioral banding (structuring amounts like ₹9k-₹10k), and temporal clusters.

### 3. "Leverage machine learning techniques for anomaly detection and predictive risk scoring"
**How FAGE solves this:**
- **Anomaly Detection:** We use a Differential Privacy-infused engine that bounds extreme outliers and zeroes in on structured evasion tactics.
- **Predictive Risk Scoring:** We don't just output `1` or `0`. We output a calibrated probability score. Furthermore, we implemented **Cost-Optimized Thresholding** that shifts the risk score boundary based on the real-world financial cost (in Rupees) of the transaction.

### 4. "Intelligent alert generation to help banks proactively detect and prevent"
**How FAGE solves this:**
- This is where FAGE destroys the competition. Standard models just send a flag (which causes alert fatigue).
- **Intelligent Alert Generation:** FAGE groups related alerts using a **Multi-Hop Network Graph**. Instead of flagging 5 separate transactions, FAGE intelligently generates *one* alert that maps the entire mule ring.
- Furthermore, we integrated **NVIDIA NIM LLMs** with NeMo Guardrails to automatically draft human-readable Suspicious Activity Reports (SARs) from those intelligent alerts.

### 5. "Perform feature engineering... to accurately distinguish suspicious accounts from legitimate ones"
**How FAGE solves this:**
- We didn't just throw raw data into a neural network. We engineered features that represent actual money laundering typologies:
  - High-velocity synchronized transfers.
  - Near-threshold structuring (smurfing).
  - Graph-based bridge node activity.
- We used **SHAP (SHapley Additive exPlanations)** to legally prove to regulators *which* engineered features caused an account to be classified as suspicious. 

---

## How to use this during the pitch:
If a judge asks: *"This is a lot of fancy tech, but did you do the feature engineering and classification we asked for?"*

**Your Answer:**
> *"Yes, absolutely. The core of FAGE is exactly what was requested: a classification engine that performs predictive risk scoring and feature engineering on your dataset. We extracted time-velocity and structuring features to build our XGBoost classifier.* 
> *However, we realized that simply answering the prompt wasn't enough to help a real bank. A raw classification model just generates more work for analysts. So we built the **Network Graph** and **LLM Alert Generation** on top of our classifier to ensure that when our model finds a mule account, the bank has the tools to actually stop it in real-time."*
