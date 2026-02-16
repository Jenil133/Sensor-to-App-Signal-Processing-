import threading
from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.anomaly.engine import run_detectors
from app.constants import CLEAN_SPEC, PIPELINE_REPROCESS_DAYS
from app.database import SessionLocal
from app.models import CleanSample, Sample
from app.processing.aggregate import compute_daily
from app.processing.baselines import update_baseline_and_z
from app.processing.filters import clean_stream

# Single-process guard: a manual /pipeline/run must not race the post-ingest
# auto-run. Multi-worker deployments would need a DB advisory lock (out of scope).
_run_lock = threading.Lock()
_pending_users: set[str] = set()
_pending_lock = threading.Lock()

# Patched to the test session factory by conftest; production uses app.database.
session_factory = SessionLocal


def refresh_clean(db: Session, user_id: str, since: datetime) -> int:
    """Re-filter raw samples >= since into clean_samples (delete-then-insert)."""
    # Floor to the minute: resampling emits minute-floored bins, so the
    # select/delete/insert windows must align or a boundary-minute bin lands
    # below the delete window and re-runs violate uq_clean_dedupe.
    since = since.replace(second=0, microsecond=0)
    total = 0
    for metric, spec in CLEAN_SPEC.items():
        rows = db.execute(
            select(Sample.ts, Sample.value)
            .where(Sample.user_id == user_id, Sample.metric == metric,
                   Sample.ts >= since)
            .order_by(Sample.ts)
        ).all()
        if not rows:
            continue
        # utc=True treats SQLite's naive (UTC wall clock) and Postgres' aware
        # timestamps identically
        idx = pd.to_datetime([ts for ts, _ in rows], utc=True)
        cleaned = clean_stream(pd.Series([v for _, v in rows], index=idx), spec)
        db.execute(delete(CleanSample).where(CleanSample.user_id == user_id,
                                             CleanSample.metric == metric,
                                             CleanSample.ts >= since))
        db.add_all([CleanSample(user_id=user_id, metric=metric,
                                ts=ts.to_pydatetime(), value=float(v))
                    for ts, v in cleaned.items()])
        db.flush()
        total += len(cleaned)
    return total


def run_pipeline(user_id: str) -> dict:
    """filter -> aggregate -> baseline -> detect over the trailing recompute window.

    Opens its own session (safe from BackgroundTasks after the request session
    closed); serialized by the module lock; delete-then-insert everywhere makes
    re-runs idempotent.
    """
    with _run_lock:
        return _run_pipeline_locked(user_id)


def _run_pipeline_locked(user_id: str) -> dict:
        db = session_factory()
        try:
            now = datetime.now(timezone.utc)
            since = now - timedelta(days=PIPELINE_REPROCESS_DAYS)
            clean_rows = refresh_clean(db, user_id, since)
            daily_rows = 0
            day_list = [since.date() + timedelta(days=i)
                        for i in range((now.date() - since.date()).days + 1)]
            for day in day_list:
                daily_rows += compute_daily(db, user_id, day)
            for metric in ("resting_hr", "hrv_night", "skin_temp_night", "motion_total"):
                for day in day_list:  # chronological: baselines never see the future
                    update_baseline_and_z(db, user_id, metric, day)
            events_created = run_detectors(db, user_id)
            db.commit()
            return {"clean_rows": clean_rows, "daily_rows": daily_rows,
                    "events_created": events_created}
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


def run_pipeline_background(user_id: str) -> None:
    """Post-ingest auto-run. At most one queued run per user: a run that is
    already waiting will see this ingest's data anyway, so extra callers return
    instead of stacking request threads behind the lock."""
    with _pending_lock:
        if user_id in _pending_users:
            return
        _pending_users.add(user_id)
    try:
        with _run_lock:
            with _pending_lock:
                _pending_users.discard(user_id)  # running now; later ingests may queue anew
            _run_pipeline_locked(user_id)
    except Exception:
        with _pending_lock:
            _pending_users.discard(user_id)
        raise
