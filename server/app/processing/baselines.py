from datetime import date
from statistics import median

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.constants import BASELINE_MIN_DAYS, BASELINE_WINDOW_DAYS, MIN_SPREAD
from app.models import BaselineRow, DailyMetric


def update_baseline_and_z(db: Session, user_id: str, metric: str, day: date) -> None:
    """Rolling personal baseline for one (metric, day): trailing 14-day median
    + 1.4826*MAD spread, then z for that day.

    The window is strictly BEFORE `day` — a baseline must never include the
    day it judges, or a shift contaminates its own reference. The MIN_SPREAD
    floor stops near-zero MAD from turning normal jitter into z = 15.
    """
    prior = [v for (v,) in db.execute(
        select(DailyMetric.value).where(
            DailyMetric.user_id == user_id,
            DailyMetric.metric == metric,
            DailyMetric.day < day,
        ).order_by(DailyMetric.day.desc()).limit(BASELINE_WINDOW_DAYS)
    ).all()]
    if len(prior) < BASELINE_MIN_DAYS:
        return
    center = median(prior)
    spread = max(1.4826 * median([abs(v - center) for v in prior]), MIN_SPREAD[metric])
    db.execute(delete(BaselineRow).where(BaselineRow.user_id == user_id,
                                         BaselineRow.metric == metric,
                                         BaselineRow.as_of_day == day))
    db.add(BaselineRow(user_id=user_id, metric=metric, as_of_day=day,
                       center=center, spread=spread,
                       window_days=BASELINE_WINDOW_DAYS))
    row = db.execute(select(DailyMetric).where(DailyMetric.user_id == user_id,
                                               DailyMetric.metric == metric,
                                               DailyMetric.day == day)).scalar_one_or_none()
    if row is not None:
        row.z = (row.value - center) / spread
    db.flush()
