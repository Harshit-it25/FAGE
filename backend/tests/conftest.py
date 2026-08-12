import os
os.environ.setdefault("FAGE_ENV", "test")
# Isolate tests from the real demo database (fage_alerts.db) -- previously, running pytest
# inserted real TXN-TEST-*/TXN-DUP-* rows directly into the live demo DB used for the actual
# hackathon demo, silently polluting it on every CI run. Must be set before any app module
# (which reads DATABASE_URL at import time) is imported.
os.environ.setdefault("DATABASE_URL", "sqlite:///./fage_alerts_test.db")
