from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

# SQLite allows one writer at a time; a generous busy timeout lets ingest
# writes wait out a background pipeline run instead of erroring. No-op for
# Postgres, which handles concurrent writers natively.
_connect_args = {"timeout": 60} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, pool_pre_ping=True,
                       connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
