from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import STREAM_BOUNDS
from app.models import RawPayload, Sample
from app.schemas import IngestIn


def _utc_key(ts: datetime) -> datetime:
    """Normalize to naive-UTC so keys compare identically across Postgres
    (returns tz-aware) and SQLite (returns naive, already UTC wall clock)."""
    if ts.tzinfo is not None:
        ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
    return ts


def process_payload(db: Session, payload: RawPayload, body: IngestIn) -> dict:
    """Validate bounds, dedupe against existing rows, bulk-insert samples.

    Contract (Phase 2 depends on it): inserts into `samples` only; never
    filters/aggregates. Returns {stored, dropped_out_of_range, dropped_duplicates}.
    """
    try:
        # Normalize timestamps to UTC once, up front: bounds, dedupe keys and
        # inserted rows must all use the same clock or SQLite (which stores the
        # raw wall clock) misses duplicates sent with a non-UTC offset.
        kept: list = []
        dropped_out_of_range = 0
        for s in body.samples:
            lo, hi = STREAM_BOUNDS[s.metric]
            if lo <= s.value <= hi:
                kept.append((s.metric, s.ts.astimezone(timezone.utc), s.value))
            else:
                dropped_out_of_range += 1  # dropped, never clamped

        stored = 0
        dropped_duplicates = 0
        if kept:
            ts_lo = min(ts for _, ts, _ in kept)
            ts_hi = max(ts for _, ts, _ in kept)
            existing = {
                (metric, _utc_key(ts))
                for metric, ts in db.execute(
                    select(Sample.metric, Sample.ts).where(
                        Sample.device_id == payload.device_id,
                        Sample.ts >= ts_lo,
                        Sample.ts <= ts_hi,
                    )
                ).all()
            }
            rows = []
            seen: set = set()
            for metric, ts, value in kept:
                key = (metric, _utc_key(ts))
                if key in existing or key in seen:
                    dropped_duplicates += 1
                    continue
                seen.add(key)
                rows.append(Sample(user_id=payload.user_id, device_id=payload.device_id,
                                   metric=metric, ts=ts, value=value))
            db.add_all(rows)
            db.flush()  # surface constraint violations here, inside the error handler
            stored = len(rows)

        payload.processed = True
        return {"stored": stored,
                "dropped_out_of_range": dropped_out_of_range,
                "dropped_duplicates": dropped_duplicates}
    except Exception as exc:
        db.rollback()
        # Rollback discarded the pending payload insert too; re-persist the
        # encrypted blob with the error recorded so it can be reprocessed.
        payload.processed = False
        payload.error = str(exc)[:500]
        db.add(payload)
        db.commit()
        raise
