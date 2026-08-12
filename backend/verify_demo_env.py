import os
import sys
import json
import hashlib
from pathlib import Path
import ctypes

def get_hash(filepath):
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()

def is_admin():
    try:
        return os.getuid() == 0
    except AttributeError:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0

def run_checks():
    errors = []
    
    print("=========================================")
    print("FAGE SECURITY SELF-CHECK (DEMO ENVIRONMENT)")
    print("=========================================")

    # 1. OS Privilege
    if is_admin():
        errors.append("Application is running as Root/Administrator. Must drop privileges for demo.")
    else:
        print("[OK] Running as standard non-privileged user.")

    # 2. Production Environment
    env = os.environ.get("FAGE_ENV", "").lower()
    if env != "production":
        errors.append(f"FAGE_ENV is not 'production' (current: {env}).")
    else:
        print("[OK] FAGE_ENV is production.")

    # 3. Secure JWT Secret
    secret = os.environ.get("FAGE_JWT_SECRET")
    if not secret or secret == "fage-dev-jwt-secret-change-in-production":
        errors.append("FAGE_JWT_SECRET is missing or insecure.")
    else:
        print("[OK] Secure FAGE_JWT_SECRET is configured.")

    # 4. Demo Database
    db_path = Path("fage_alerts.db")
    if not db_path.exists():
        errors.append("Demo database (fage.db) is missing.")
    else:
        print(f"[OK] Demo database exists (Size: {db_path.stat().st_size / 1024 / 1024:.2f} MB).")

    # 5. Frontend Build Secrets Check
    frontend_dist = Path("../frontend/dist")
    if frontend_dist.exists():
        found_secrets = False
        for ext in ["*.js", "*.html"]:
            for file in frontend_dist.rglob(ext):
                content = file.read_text(encoding="utf-8", errors="ignore")
                # Searching for the literal default secret to ensure it didn't get compiled in
                if "fage-dev-jwt-secret" in content or "NVIDIA_API_KEY" in content:
                    found_secrets = True
        if found_secrets:
            errors.append("Frontend build contains hardcoded secrets or environment variables.")
        else:
            print("[OK] Frontend bundle is free of backend secrets.")
            
        # 6. Database / Env in Frontend Static Directory
        if (frontend_dist / "fage.db").exists() or (frontend_dist / ".env").exists():
            errors.append("Sensitive files (.db / .env) found in frontend static directory.")
        else:
            print("[OK] Static directory does not contain sensitive files.")
    else:
        errors.append("Frontend dist directory not found. Please build the frontend.")

    # 7. Model Integrity
    model_path = Path("models/xgboost_classifier.pkl")
    model_hash = get_hash(model_path)
    if not model_hash:
        errors.append("Model artifact missing.")
    else:
        print(f"[OK] Model artifact present. (Hash: {model_hash[:8]}...)")

    print("=========================================")
    if errors:
        print("ENVIRONMENT VALIDATION FAILED:")
        for err in errors:
            print(f"  [!] {err}")
        sys.exit(1)
    else:
        print("ENVIRONMENT VALIDATION PASSED. (Ready for Demo)")
        sys.exit(0)

if __name__ == "__main__":
    run_checks()
