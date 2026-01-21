from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AwareDatetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import STREAM_BOUNDS
from app.database import get_db
from app.deps import get_current_user
from app.models import Sample, User
from app.schemas import SamplePoint

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
