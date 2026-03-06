import os

from cryptography.fernet import Fernet

# Must be set BEFORE importing anything from app — Settings and Fernet
# initialize at import time.
os.environ["PAYLOAD_ENC_KEY"] = Fernet.generate_key().decode()
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-secret-0123456789abcdef0123456789abcdef"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models import Base
from app.processing import jobs

engine = create_engine("sqlite://", poolclass=StaticPool,
                       connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base.metadata.create_all(engine)  # tests bypass Alembic intentionally

jobs.session_factory = TestingSessionLocal  # pipeline runs against the test DB

app.state.limiter.enabled = False  # rate limits are checked manually, not in the suite


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
