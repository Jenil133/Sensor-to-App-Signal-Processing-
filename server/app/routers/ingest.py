from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.crypto import canonical_bytes, encrypt, sha256_hex
from app.database import get_db
from app.deps import get_current_device
from app.models import Device, RawPayload
from app.processing.intake import process_payload
from app.schemas import IngestIn, IngestOut

router = APIRouter(prefix="/api/v1", tags=["ingest"])


@router.post("/ingest", status_code=202, response_model=IngestOut)
def ingest(body: IngestIn, db: Session = Depends(get_db),
           device: Device = Depends(get_current_device)):
    plaintext = canonical_bytes(body.model_dump(mode="json"))
    payload = RawPayload(user_id=device.user_id, device_id=device.id,
                         ciphertext=encrypt(plaintext), sha256=sha256_hex(plaintext),
                         sample_count=len(body.samples))
    db.add(payload)
    db.flush()          # get payload.id before intake
    result = process_payload(db, payload, body)   # synchronous in Phase 1 — fine at demo scale
    db.commit()
    return IngestOut(payload_id=payload.id, **result)
