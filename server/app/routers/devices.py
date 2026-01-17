from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Device, User
from app.schemas import DeviceCreateIn, DeviceOut, DeviceWithTokenOut
from app.security import generate_device_token, hash_device_token

router = APIRouter(prefix="/api/v1", tags=["devices"])


@router.post("/devices", status_code=201, response_model=DeviceWithTokenOut)
def create_device(body: DeviceCreateIn, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    token = generate_device_token()
    device = Device(user_id=user.id, name=body.name, token_hash=hash_device_token(token))
    db.add(device)
    db.commit()
    db.refresh(device)
    return DeviceWithTokenOut(id=device.id, name=device.name,
                              created_at=device.created_at,
                              last_seen_at=device.last_seen_at,
                              device_token=token)


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.execute(
        select(Device).where(Device.user_id == user.id).order_by(Device.created_at)
    ).scalars().all()
