from datetime import date, datetime

from pydantic import (AwareDatetime, BaseModel, ConfigDict, EmailStr, Field,
                      field_validator)

from app.constants import MAX_BATCH_SAMPLES, STREAM_BOUNDS


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def password_within_bcrypt_limit(cls, v: str) -> str:
        # bcrypt's limit is 72 BYTES; multibyte UTF-8 can exceed it within 72 chars
        if len(v.encode("utf-8")) > 72:
            raise ValueError("password must be at most 72 bytes when UTF-8 encoded")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DeviceCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    created_at: datetime
    last_seen_at: datetime | None


class DeviceWithTokenOut(DeviceOut):
    device_token: str  # returned exactly once, at creation


class SampleIn(BaseModel):
    metric: str
    ts: AwareDatetime
    value: float

    @field_validator("metric")
    @classmethod
    def metric_must_be_known(cls, v: str) -> str:
        if v not in STREAM_BOUNDS:
            raise ValueError(f"unknown metric {v!r}")
        return v


class IngestIn(BaseModel):
    device_time: AwareDatetime
    samples: list[SampleIn] = Field(min_length=1, max_length=MAX_BATCH_SAMPLES)


class IngestOut(BaseModel):
    payload_id: str
    stored: int
    dropped_out_of_range: int
    dropped_duplicates: int


class SamplePoint(BaseModel):
    ts: datetime
    value: float


class DailyPoint(BaseModel):
    day: date
    value: float
    z: float | None
    baseline_center: float | None
    baseline_spread: float | None


class AnomalyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    metric: str | None
    detector: str
    severity: str
    score: float
    started_at: date
    ended_at: date | None
    status: str
    details: dict
    created_at: datetime


class AnomalyAckOut(BaseModel):
    id: str
    status: str


class PipelineRunOut(BaseModel):
    clean_rows: int
    daily_rows: int
    events_created: int
