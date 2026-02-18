from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import AnomalyEvent, User
from app.schemas import AnomalyAckOut, AnomalyOut

router = APIRouter(prefix="/api/v1", tags=["anomalies"])

VALID_STATUSES = {"open", "resolved", "acked"}


@router.get("/anomalies", response_model=list[AnomalyOut])
def list_anomalies(status: str | None = None, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(status_code=422,
                            detail=f"status must be one of {sorted(VALID_STATUSES)}")
    query = select(AnomalyEvent).where(AnomalyEvent.user_id == user.id)
    if status is not None:
        query = query.where(AnomalyEvent.status == status)
    return db.execute(
        query.order_by(AnomalyEvent.created_at.desc())
    ).scalars().all()


@router.post("/anomalies/{anomaly_id}/ack", response_model=AnomalyAckOut)
def ack_anomaly(anomaly_id: str, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    event = db.get(AnomalyEvent, anomaly_id)
    if event is None or event.user_id != user.id:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    event.status = "acked"
    db.commit()
    return AnomalyAckOut(id=event.id, status=event.status)
