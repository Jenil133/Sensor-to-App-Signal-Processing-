import os

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import DERIVED_METRICS, ISOFOREST_TRAIN_DAYS
from app.database import get_db
from app.deps import get_current_user
from app.models import DailyMetric, ModelArtifact, User
from app.schemas import TrainOut

router = APIRouter(prefix="/api/v1", tags=["models"])

MIN_TRAIN_DAYS = 35


def z_matrix(db: Session, user_id: str) -> np.ndarray:
    """(days, 4) matrix of derived-metric z's, complete rows only, day order."""
    rows = db.execute(
        select(DailyMetric.day, DailyMetric.metric, DailyMetric.z)
        .where(DailyMetric.user_id == user_id, DailyMetric.z.is_not(None))
        .order_by(DailyMetric.day)
    ).all()
    if not rows:
        return np.empty((0, 4))
    frame = pd.DataFrame(rows, columns=["day", "metric", "z"])
    latest = frame["day"].max()
    frame = frame[frame["day"] > latest - pd.Timedelta(days=ISOFOREST_TRAIN_DAYS)]
    # Reindex to ALL four derived metrics before dropna: a user missing one
    # metric entirely must yield zero complete rows (-> 422), not a 3-column
    # matrix that crashes the 28-input autoencoder with a 500.
    pivot = (frame.pivot(index="day", columns="metric", values="z")
             .reindex(columns=sorted(DERIVED_METRICS)).dropna())
    return pivot.to_numpy(dtype="float64")


@router.post("/models/train", response_model=TrainOut)
def train_model(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not settings.enable_autoencoder:
        raise HTTPException(status_code=409, detail="autoencoder disabled")
    try:
        from app.anomaly import autoencoder
        z = z_matrix(db, user.id)
        if len(z) < MIN_TRAIN_DAYS:
            raise HTTPException(
                status_code=422,
                detail=f"insufficient history: {len(z)} complete days, need {MIN_TRAIN_DAYS}")
        model, _threshold, metrics = autoencoder.train(z)
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="torch not installed — pip install 'torch>=2.3' "
                   "--index-url https://download.pytorch.org/whl/cpu")
    prev = db.execute(
        select(ModelArtifact.version)
        .where(ModelArtifact.user_id == user.id, ModelArtifact.detector == "autoencoder")
        .order_by(ModelArtifact.version.desc()).limit(1)
    ).scalar_one_or_none()
    version = (prev or 0) + 1
    user_dir = os.path.join(settings.models_dir, user.id)
    os.makedirs(user_dir, exist_ok=True)
    path = os.path.join(user_dir, f"ae_v{version}.pt")
    autoencoder.save_checkpoint(model, path)
    db.add(ModelArtifact(user_id=user.id, detector="autoencoder", version=version,
                         path=path, metrics=metrics))
    db.commit()
    return TrainOut(version=version, n_windows=metrics["n_windows"],
                    train_mse=metrics["train_mse"], threshold=metrics["threshold"])
