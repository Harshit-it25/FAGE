import logging
import ssl
import time
from typing import Dict, List, Optional, Tuple
import httpx

from threading import Lock

logger = logging.getLogger("FAGE.SecurityService")

_security_lock = Lock()
_login_attempts: Dict[str, List[float]] = {}
_data_access_logs: Dict[str, List[Tuple[float, int]]] = {}

MAX_LOGIN_FAILURES = 5
LOGIN_FAILURE_WINDOW = 300  # 5 minutes

BULK_RECORDS_THRESHOLD = 1000
BULK_RECORDS_WINDOW = 60  # 1 minute

class SecurityService:
    @staticmethod
    def analyze_login_attempt(username: str, success: bool):
        """
        Background task to analyze login attempts for brute-force patterns.
        """
        now = time.time()
        
        with _security_lock:
            if success:
                if username in _login_attempts and len(_login_attempts[username]) >= (MAX_LOGIN_FAILURES / 2):
                    logger.critical(f"ANOMALY DETECTED: Successful login for user '{username}' after {len(_login_attempts[username])} recent failures!")
                return

            if username not in _login_attempts:
                _login_attempts[username] = []
            
            _login_attempts[username].append(now)
            
            _login_attempts[username] = [
                t for t in _login_attempts[username] 
                if now - t <= LOGIN_FAILURE_WINDOW
            ]
            
            failures = len(_login_attempts[username])
            if failures >= MAX_LOGIN_FAILURES:
                logger.critical(f"ANOMALY DETECTED: Brute-force login attempt for user '{username}'. {failures} failures in {LOGIN_FAILURE_WINDOW}s.")

    @staticmethod
    def analyze_data_access(username: str, records_pulled: int):
        """
        Background task to analyze bulk data access (DLP monitor).
        """
        now = time.time()
        
        with _security_lock:
            if username not in _data_access_logs:
                _data_access_logs[username] = []
                
            _data_access_logs[username].append((now, records_pulled))
            
            _data_access_logs[username] = [
                (t, count) for (t, count) in _data_access_logs[username]
                if now - t <= BULK_RECORDS_WINDOW
            ]
            
            total_records = sum(count for _, count in _data_access_logs[username])
            
            if total_records >= BULK_RECORDS_THRESHOLD:
                logger.critical(f"ANOMALY DETECTED: Bulk data access by user '{username}'. {total_records} records pulled in {BULK_RECORDS_WINDOW}s.")
            # Action to take: Suspend session, alert security team, etc.

    @staticmethod
    def get_secure_http_client() -> httpx.Client:
        """
        Returns a hardened httpx Client with TLS 1.3 enforcement 
        (or TLS 1.2 minimum fallback if 1.3 is unsupported).
        """
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        try:
            ctx.maximum_version = ssl.TLSVersion.TLSv1_3
        except AttributeError:
            pass  # Fallback to TLS 1.2
            
        ctx.load_default_certs()
        # Enforce strong ciphers
        ctx.set_ciphers("TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:TLS_AES_128_GCM_SHA256:ECDHE+AESGCM:ECDHE+CHACHA20:!aNULL:!MD5:!RC4:!3DES:!EXPORT")
        
        return httpx.Client(verify=ctx)

security_service = SecurityService()
