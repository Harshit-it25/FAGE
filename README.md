# FAGE: Fraud Analytics & Governance Engine 🛡️

FAGE is an enterprise-grade Fraud Analytics & Governance Engine designed for high-dimensional risk scoring, anomaly detection, rule-based policy compliance, and explainable AI (SHAP attributions) to identify mule accounts.

The project features a **FastAPI backend** that processes raw transaction telemetry, runs ML classification/unsupervised outliers detection, and exposes clean REST APIs, paired with a **React + TypeScript + Vite frontend** that displays operational logs, alert queues, risk scorecards, and model telemetry dashboards.

---

## Key Features

- **Multi-Model Ensemble Scoring**: Integrates XGBoost, LightGBM, RandomForest, and ExtraTrees pipelines to evaluate transaction profiles.
- **Explainable AI (SHAP Attributions)**: Computes local Shapley values and produces waterfall waterfall attributions detailing the exact variables driving risks.
- **Rule-Based Compliance Overrides**: Evaluates geographical, monetary volume, and velocity threshold policies to override machine learning models instantly where regulation mandates.
- **Interactive Operations Workbench**: Provides real-time status management, operator assignments, case note recording, and metrics profiling.
- **Zero-Config Developer Fallbacks**: Automatically deploys mock preprocessor/scoring proxies if local binary model (`.pkl`) files haven't been compiled yet, enabling the full UI to run out-of-the-box.

---

## Getting Started

### Prerequisites

Ensure you have the following installed on your system:
- **Node.js** (v18.0.0 or higher)
- **Python** (v3.9 or higher)

---

### Step 1: Install Dependencies

#### Frontend (Node.js)
From the root directory of the project, run:
```bash
npm install
```

#### Backend (Python)
Navigate to the `backend` directory and install the required libraries:
```bash
cd backend
pip install -r requirements.txt
```

---

### Step 2: Running the Application

For a quick setup, you can launch both services together.

#### On Windows
Run the pre-configured batch file in the root directory:
```bash
start.bat
```

#### Manual Run (Any OS)
If you prefer to run the services in separate terminal windows:

1. **Launch FastAPI Backend** (Port 8000):
   ```bash
   cd backend
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
2. **Launch Vite Frontend Dev Server** (Port 3000):
   ```bash
   # From root directory
   npm run dev
   ```

Open your browser to `http://localhost:3000`. The frontend is preconfigured to proxy API calls (`/api/...`) to the backend at `http://localhost:8000`.

---

## Directory Structure

```
├── backend/
│   ├── app/
│   │   ├── ml/                 # Custom preprocessing, selection, & SHAP engines
│   │   ├── services/           # Unified Risk Engine logic
│   │   ├── main.py             # FastAPI App router
│   │   └── target_alerts.json  # Stored alert logs database
│   ├── train_models.py         # Model training script
│   └── requirements.txt        # Backend python dependencies
├── src/
│   ├── components/             # React views (Dashboard, Alert Queue, Insights, Workbench)
│   ├── services/               # API clients and TypeScript interface contracts
│   ├── App.tsx                 # UI Shell and Route logic
│   └── index.css               # Tailored global styles
├── start.bat                   # Automation startup script
└── vite.config.ts              # Vite bundle configuration and dev API proxying
```
