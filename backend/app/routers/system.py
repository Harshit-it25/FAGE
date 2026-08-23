from __future__ import annotations
import os
import sys
import json
import pickle
import logging
import uuid
import time
import hashlib
import threading
import asyncio
import io
import random
from datetime import datetime, UTC
from fastapi import APIRouter
from app.dependencies import risk_engine, _active_alert_score_cutoffs

router = APIRouter(tags=["System"])

@router.get("/", tags=["System"])
def index():
    return {
        "engine": "FAGE (Fraud Analytics & Governance Engine)",
        "status": "online",
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_loaded": risk_engine.default_model_name,
        "is_fallback_active": not risk_engine.is_production_ready
    }

@router.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "service": "fage-backend",
        "version": "2.0.0",
        "model_ready": risk_engine.is_production_ready
    }

@router.get("/config", tags=["System"])
def get_config():
    medium_cutoff, high_cutoff = _active_alert_score_cutoffs()
    return {
        "medium_cutoff": medium_cutoff,
        "high_cutoff": high_cutoff
    }

