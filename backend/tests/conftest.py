import os
os.environ.setdefault("FAGE_ENV", "test")
os.environ["DATABASE_URL"] = "sqlite:///./fage_alerts_test.db"

import pytest
from app.db import Base, engine, ensure_schema_columns

@pytest.fixture(autouse=True, scope="session")
def setup_db_session():
    # Ensure a completely pristine test database per test session
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    ensure_schema_columns(engine)
