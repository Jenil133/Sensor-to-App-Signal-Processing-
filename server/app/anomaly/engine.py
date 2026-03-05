import logging
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.anomaly.cusum import cusum_alarms
from app.anomaly.isoforest import isoforest_flags
from app.config import settings
from app.constants import (CUSUM_H, CUSUM_K, DERIVED_METRICS,
                           ISOFOREST_TRAIN_DAYS, ZSCORE_HIGH, ZSCORE_MED)
from app.models import AnomalyEvent, DailyMetric, ModelArtifact

logger = logging.getLogger(__name__)

DETECTOR_LOOKBACK_DAYS = 60
QUIET_DAYS_TO_RESOLVE = 2


def _apply_lifecycle(db: Session, user_id: str, detector: str, metric: str | None,
                     firing: bool, *, started_at: date | None = None,
                     score: float = 0.0, severity: str = "med",
                     details: dict | None = None,
                     last_fire_day: date | None = None) -> int:
    """Open -> resolved/acked event lifecycle shared by every detector.

    Firing + open event: update score/details, keep the original started_at.
    Firing + none open: insert — unless the latest event for this
    (detector, metric) is acked and still unresolved (acked never reopens).
    Not firing (for >= 2 quiet days, checked by the caller) + open: resolve.
    Returns 1 if a new event was created.
    """
    metric_clause = (AnomalyEvent.metric.is_(None) if metric is None
                     else AnomalyEvent.metric == metric)
    open_ev = db.execute(
        select(AnomalyEvent).where(AnomalyEvent.user_id == user_id,
                                   AnomalyEvent.detector == detector,
                                   metric_clause,
                                   AnomalyEvent.status == "open")
    ).scalar_one_or_none()
    if firing:
        if open_ev is not None:
            open_ev.score = score
            open_ev.severity = severity
            open_ev.details = details or {}
            db.flush()
            return 0
        latest = db.execute(
            select(AnomalyEvent).where(AnomalyEvent.user_id == user_id,
                                       AnomalyEvent.detector == detector,
                                       metric_clause)
            .order_by(AnomalyEvent.created_at.desc()).limit(1)
        ).scalar_one_or_none()
        if latest is not None and latest.status == "acked" and latest.ended_at is None:
            return 0  # user acknowledged this ongoing episode; stay quiet
        db.add(AnomalyEvent(user_id=user_id, metric=metric, detector=detector,
                            severity=severity, score=score,
                            started_at=started_at or last_fire_day or date.today(),
                            details=details or {}))
        db.flush()
        return 1
    # Quiet: close the current episode. Open events resolve; an acked episode
    # gets its ended_at stamped (status stays acked) so a FUTURE shift can open
    # a fresh event — otherwise one ack would mute this pair forever.
    if last_fire_day is not None:
        for ev in (open_ev,) if open_ev is not None else ():
            ev.ended_at = max(last_fire_day, ev.started_at)  # never invert the interval
            ev.status = "resolved"
        acked_open = db.execute(
            select(AnomalyEvent).where(AnomalyEvent.user_id == user_id,
                                       AnomalyEvent.detector == detector,
                                       metric_clause,
                                       AnomalyEvent.status == "acked",
                                       AnomalyEvent.ended_at.is_(None))
        ).scalars().all()
        for ev in acked_open:
            ev.ended_at = max(last_fire_day, ev.started_at)
        db.flush()
    return 0


def run_detectors(db: Session, user_id: str) -> int:
    """Run zscore, CUSUM and IsolationForest over recent daily z-series.

    A detector is "firing" when its signal touches the last QUIET_DAYS_TO_RESOLVE
    days of the series; an open event with no firing in that window resolves.
    Returns the number of events created.
    """
    rows = db.execute(
        select(DailyMetric.metric, DailyMetric.day, DailyMetric.z)
        .where(DailyMetric.user_id == user_id, DailyMetric.z.is_not(None))
        .order_by(DailyMetric.day)
    ).all()
    if not rows:
        return 0
    latest_day = max(day for _, day, _ in rows)
    lookback = latest_day - timedelta(days=DETECTOR_LOOKBACK_DAYS)
    iso_lookback = latest_day - timedelta(days=ISOFOREST_TRAIN_DAYS)
    created = 0

    for metric in DERIVED_METRICS:
        series = [(day, z) for m, day, z in rows if m == metric and day > lookback]
        if not series:
            continue
        days = [d for d, _ in series]
        zs = [z for _, z in series]

        # zscore: per-day threshold on |z|; onset = start of the current run
        fire_flags = [abs(z) >= ZSCORE_MED for z in zs]
        firing = any(fire_flags[-QUIET_DAYS_TO_RESOLVE:])
        fire_idx = next((i for i in range(len(days) - 1, -1, -1) if fire_flags[i]), None)
        last_fire = days[fire_idx] if fire_idx is not None else None
        onset = None
        if firing:
            i = fire_idx
            while i > 0 and fire_flags[i - 1]:
                i -= 1
            onset = days[i]
        # score/severity from the day that actually crossed the threshold —
        # not the latest day, which may be the quiet one after a spike
        fire_z = zs[fire_idx] if fire_idx is not None else zs[-1]
        fire_abs_z = abs(fire_z)
        created += _apply_lifecycle(
            db, user_id, "zscore", metric, firing,
            started_at=onset, score=fire_abs_z,
            severity="high" if fire_abs_z >= ZSCORE_HIGH else "med",
            details={"z": round(fire_z, 2), "threshold": ZSCORE_MED},
            last_fire_day=last_fire)

        # cusum: sustained-shift accumulation on the z series
        alarms = cusum_alarms(zs, CUSUM_K, CUSUM_H)
        last_alarm = alarms[-1] if alarms else None
        cusum_firing = (last_alarm is not None
                        and last_alarm["index"] >= len(zs) - QUIET_DAYS_TO_RESOLVE)
        created += _apply_lifecycle(
            db, user_id, "cusum", metric, cusum_firing,
            started_at=days[min(last_alarm["onset_index"], len(days) - 1)] if last_alarm else None,
            score=last_alarm["statistic"] if last_alarm else 0.0,
            severity=("high" if last_alarm and last_alarm["statistic"] > 1.5 * CUSUM_H
                      else "med"),
            details=({"direction": last_alarm["direction"],
                      "statistic": last_alarm["statistic"],
                      "k": CUSUM_K, "h": CUSUM_H} if last_alarm else {}),
            last_fire_day=days[last_alarm["index"]] if last_alarm else None)

    # isolation forest: multivariate over the four derived z's
    iso_rows = [(day, m, z) for m, day, z in rows if day > iso_lookback]
    frame = pd.DataFrame(iso_rows, columns=["day", "metric", "z"])
    feature_df = frame.pivot(index="day", columns="metric", values="z")
    flags = isoforest_flags(feature_df)
    last_flag = flags[-1] if flags else None
    iso_firing = (last_flag is not None
                  and last_flag["day"] >= latest_day - timedelta(days=QUIET_DAYS_TO_RESOLVE - 1))
    created += _apply_lifecycle(
        db, user_id, "isolation_forest", None, iso_firing,
        started_at=last_flag["day"] if last_flag else None,
        score=abs(last_flag["score"]) if last_flag else 0.0,
        severity="med",
        details=({"top_feature": last_flag["top_feature"],
                  "score": round(last_flag["score"], 4)} if last_flag else {}),
        last_fire_day=last_flag["day"] if last_flag else None)

    # autoencoder (detector #4, flag-gated): reconstruction error of the
    # latest 7-day window vs the user's trained threshold
    if settings.enable_autoencoder:
        created += _run_autoencoder(db, user_id, feature_df, latest_day)
    return created


def _run_autoencoder(db: Session, user_id: str, feature_df: pd.DataFrame,
                     latest_day: date) -> int:
    artifact = db.execute(
        select(ModelArtifact)
        .where(ModelArtifact.user_id == user_id,
               ModelArtifact.detector == "autoencoder")
        .order_by(ModelArtifact.version.desc()).limit(1)
    ).scalar_one_or_none()
    if artifact is None:
        return 0
    complete = feature_df.dropna().reindex(sorted(feature_df.columns), axis=1)
    if len(complete) < 7:
        return 0
    try:
        from app.anomaly import autoencoder
        model = autoencoder.load_checkpoint(artifact.path)
        score = autoencoder.score_latest(model, complete.to_numpy(dtype="float64"))
    except Exception as exc:  # missing wheel, missing file, corrupt checkpoint
        logger.warning("autoencoder skipped for user %s: %s", user_id, exc)
        return 0
    threshold = float(artifact.metrics.get("threshold", float("inf")))
    firing = score > threshold
    return _apply_lifecycle(
        db, user_id, "autoencoder", None, firing,
        started_at=latest_day if firing else None,
        score=score,
        severity="high" if score > 2 * threshold else "med",
        details={"threshold": round(threshold, 4), "version": artifact.version,
                 "score": round(score, 4)},
        last_fire_day=latest_day)
