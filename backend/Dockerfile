FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY train_models.py .
COPY models/ ./models/
COPY fage_alerts*.db ./

# Create data directory for SQLite
RUN mkdir -p /app/data

# Run as a non-root user. The app writes fage_alerts.db and reads/writes model
# files under /app — chown so the app user can still do both after switching.
RUN useradd --create-home --shell /bin/bash fage \
    && chown -R fage:fage /app
USER fage

# Expose port
EXPOSE 8000

# Railway performs its own TCP healthchecks, so we omit Docker HEALTHCHECK to prevent conflicts.

# Run using the python script which handles PORT env var natively
CMD ["python", "run.py"]
