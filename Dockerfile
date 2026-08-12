# ==============================================================================
# FAGE - Unified Deployment Dockerfile
# ==============================================================================
FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir uvicorn

# Copy the entire backend
COPY backend/ /app/backend/

# Copy the built frontend dist folder
COPY frontend/dist/ /app/frontend/dist/

# Copy the runner script
COPY run.py /app/run.py

# Expose the standard port
EXPOSE 8000

# Set environment
ENV FAGE_ENV=dev
ENV PORT=8000

CMD ["python", "run.py"]
