import os
import sys
import uvicorn

# FAGE_ENV is no longer forced to "dev". 
# Configure it explicitly via environment variables.

# Add the backend directory to sys.path so 'app' imports resolve correctly
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from app.main import app

if __name__ == "__main__":
    os.environ.setdefault("FAGE_ENV", "development")
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting FAGE Unified Server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
