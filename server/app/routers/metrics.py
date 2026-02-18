from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AwareDatetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import DERIVED_METRICS, STREAM_BOUNDS
from app.database import get_db
from app.deps import get_current_user
from app.models import BaselineRow, DailyMetric, Sample, User
from app.schemas import DailyPoint, SamplePoint

router = APIRouter(prefix="/api/v1", tags=["metrics"])

MAX_POINTS = 20_000


@router.get("/metrics", response_model=list[SamplePoint])
def read_metrics(metric: str, start: AwareDatetime | None = None,
                 end: AwareDatetime | None = None,
                 db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    if metric not in STREAM_BOUNDS:
        raise HTTPException(status_code=422, detail=f"unknown metric {metric!r}")
    end = (end or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = (start or end - timedelta(hours=24)).astimezone(timezone.utc)
    rows = db.execute(
        select(Sample.ts, Sample.value)
        .where(Sample.user_id == user.id, Sample.metric == metric,
               Sample.ts >= start, Sample.ts <= end)
        .order_by(Sample.ts)
        .limit(MAX_POINTS)
    ).all()
    return [SamplePoint(ts=ts, value=value) for ts, value in rows]


@router.get("/daily", response_model=list[DailyPoint])
def read_daily(metric: str, start: date | None = None, end: date | None = None,
               db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    if metric not in DERIVED_METRICS:
        raise HTTPException(status_code=422, detail=f"unknown metric {metric!r}")
    end = end or datetime.now(timezone.utc).date()
    start = start or end - timedelta(days=60)
    rows = db.execute(
        select(DailyMetric, BaselineRow)
        .join(BaselineRow,
              (BaselineRow.user_id == DailyMetric.user_id)
              & (BaselineRow.metric == DailyMetric.metric)
              & (BaselineRow.as_of_day == DailyMetric.day),
              isouter=True)
        .where(DailyMetric.user_id == user.id, DailyMetric.metric == metric,
               DailyMetric.day >= start, DailyMetric.day <= end)
        .order_by(DailyMetric.day)
    ).all()
    return [DailyPoint(day=d.day, value=d.value, z=d.z,
                       baseline_center=b.center if b else None,
                       baseline_spread=b.spread if b else None)
            for d, b in rows]
