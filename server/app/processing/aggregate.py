from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.constants import DERIVED_METRICS
from app.models import CleanSample, DailyMetric


def compute_daily(db: Session, user_id: str, day: date) -> int:
    """Aggregate one UTC day of clean_samples into derived daily_metrics rows.

    Skips a metric when its window has fewer than min_bins bins (partial-day
    guard — a garbage daily value is worse than a gap). Delete-then-insert
    keeps re-runs idempotent. z is left null; baselines fill it later.
    Returns the number of rows written.
    """
    written = 0
    for name, (source, (h0, h1), min_bins, agg) in DERIVED_METRICS.items():
        lo = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(hours=h0)
        hi = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(hours=h1)
        values = [v for (v,) in db.execute(
            select(CleanSample.value).where(
                CleanSample.user_id == user_id,
                CleanSample.metric == source,
                CleanSample.ts >= lo,
                CleanSample.ts < hi,
            )
        ).all()]
        if len(values) < min_bins:
            continue
        value = sum(values) if agg == "sum" else sum(values) / len(values)
        db.execute(delete(DailyMetric).where(DailyMetric.user_id == user_id,
                                             DailyMetric.day == day,
                                             DailyMetric.metric == name))
        db.add(DailyMetric(user_id=user_id, day=day, metric=name, value=value,
                           n_samples=len(values), vmin=min(values), vmax=max(values)))
        written += 1
    db.flush()
    return written
