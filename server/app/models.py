import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (String, Float, Boolean, Integer, BigInteger, Text,
                        Date, DateTime, ForeignKey, JSON, LargeBinary,
                        UniqueConstraint, Index)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # sha256 hex
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RawPayload(Base):
    """Encrypted storage tier: the exact client batch, Fernet-encrypted at rest."""
    __tablename__ = "raw_payloads"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey("devices.id"), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)  # hash of canonical plaintext
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (Index("ix_raw_payloads_user_received", "user_id", "received_at"),)


class Sample(Base):
    """Decoded raw sensor points (pre-filtering). Phase 2 adds clean_samples."""
    __tablename__ = "samples"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"),
                                    primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    device_id: Mapped[str] = mapped_column(String(36), ForeignKey("devices.id"), nullable=False)
    metric: Mapped[str] = mapped_column(String(32), nullable=False)  # see constants.STREAM_BOUNDS
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    __table_args__ = (UniqueConstraint("device_id", "metric", "ts", name="uq_samples_dedupe"),
                      Index("ix_samples_user_metric_ts", "user_id", "metric", "ts"))


class CleanSample(Base):
    """Filtered, 1-minute-binned canonical series (output of the filtering stage)."""
    __tablename__ = "clean_samples"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"),
                                    primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    metric: Mapped[str] = mapped_column(String(32), nullable=False)   # stream metric names
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # minute bin start
    value: Mapped[float] = mapped_column(Float, nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "metric", "ts", name="uq_clean_dedupe"),
                      Index("ix_clean_user_metric_ts", "user_id", "metric", "ts"))


class DailyMetric(Base):
    """One row per user per UTC day per DERIVED metric."""
    __tablename__ = "daily_metrics"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    metric: Mapped[str] = mapped_column(String(32), nullable=False)   # DERIVED names (see constants)
    value: Mapped[float] = mapped_column(Float, nullable=False)       # headline daily number
    n_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    vmin: Mapped[float] = mapped_column(Float)
    vmax: Mapped[float] = mapped_column(Float)
    z: Mapped[float | None] = mapped_column(Float, nullable=True)     # vs baseline; null until baseline exists
    __table_args__ = (UniqueConstraint("user_id", "day", "metric", name="uq_daily"),
                      Index("ix_daily_user_metric_day", "user_id", "metric", "day"))


class BaselineRow(Base):
    __tablename__ = "baselines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    metric: Mapped[str] = mapped_column(String(32), nullable=False)   # derived names
    as_of_day: Mapped[date] = mapped_column(Date, nullable=False)     # baseline used to judge this day
    center: Mapped[float] = mapped_column(Float, nullable=False)      # trailing 14-day median (excl. as_of_day)
    spread: Mapped[float] = mapped_column(Float, nullable=False)      # 1.4826*MAD, floored per metric
    window_days: Mapped[int] = mapped_column(Integer, default=14)
    __table_args__ = (UniqueConstraint("user_id", "metric", "as_of_day", name="uq_baseline"),)


class ModelArtifact(Base):
    """One trained per-user autoencoder checkpoint. Weights live on disk under
    MODELS_DIR/{user_id}/ae_v{version}.pt; this row is the registry + threshold."""
    __tablename__ = "model_artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    detector: Mapped[str] = mapped_column(String(32), default="autoencoder")
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)  # {"train_mse","threshold","n_windows"}
    __table_args__ = (UniqueConstraint("user_id", "detector", "version", name="uq_model_version"),)


class AnomalyEvent(Base):
    __tablename__ = "anomaly_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    metric: Mapped[str | None] = mapped_column(String(32), nullable=True)  # null = multivariate
    detector: Mapped[str] = mapped_column(String(32), nullable=False)  # zscore|cusum|isolation_forest|autoencoder
    severity: Mapped[str] = mapped_column(String(8), nullable=False)   # low|med|high
    score: Mapped[float] = mapped_column(Float, nullable=False)
    started_at: Mapped[date] = mapped_column(Date, nullable=False)
    ended_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="open")    # open|resolved|acked
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    __table_args__ = (Index("ix_anomaly_user_status", "user_id", "status"),)
