@echo off
echo =======================================================================
echo               Starting FAGE (Fraud Analytics & Governance Engine)
echo =======================================================================
echo.

echo [1/2] Launching FastAPI Backend Service...
start cmd /k "cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo [2/2] Launching Vite Frontend Dev Server...
echo (This will automatically open your default browser to http://localhost:3000)
echo.
npm run dev
