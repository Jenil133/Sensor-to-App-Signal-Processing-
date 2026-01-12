import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings


def hash_password(pw: str) -> str:
    # bcrypt ignores input past 72 bytes; reject earlier at the schema level (max_length=72)
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(pw: str, pw_hash: str) -> bool:
    encoded = pw.encode()
    if len(encoded) > 72:
        # bcrypt >=5 raises past 72 bytes; no stored hash can match such a
        # password (register rejects them), so treat as a plain mismatch to
        # keep login uniformly 401 (no enumeration oracle via 500s).
        return False
    return bcrypt.checkpw(encoded, pw_hash.encode())


def create_access_token(user_id: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_min)
    return jwt.encode({"sub": user_id, "exp": exp}, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> str:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])["sub"]  # raises on bad/expired


def generate_device_token() -> str:
    return "bld_" + secrets.token_urlsafe(32)   # shown to the client exactly once


def hash_device_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()  # only the hash is stored
