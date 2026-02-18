from datetime import datetime, timezone

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Device, User
from app.security import decode_access_token, hash_device_token


def get_current_user(db: Session = Depends(get_db),
                     authorization: str | None = Header(None)) -> User:
    # Optional header + manual 401 (not FastAPI's 422 for a missing required
    # header): the frontend treats 401 as "clear token, go to /login".
    if authorization is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    try:
        user_id = decode_access_token(token)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


def get_current_device(db: Session = Depends(get_db),
                       x_device_token: str | None = Header(None, alias="X-Device-Token")) -> Device:
    if x_device_token is None:
        raise HTTPException(status_code=401, detail="Invalid device token")
    device = db.execute(
        select(Device).where(Device.token_hash == hash_device_token(x_device_token))
    ).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=401, detail="Invalid device token")
    device.last_seen_at = datetime.now(timezone.utc)  # persisted on the request's commit
    return device
