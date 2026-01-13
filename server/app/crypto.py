import hashlib
import json

from cryptography.fernet import Fernet

from app.config import settings

_fernet = Fernet(settings.payload_enc_key.encode())  # raises at import if key malformed — fail fast


def canonical_bytes(payload: dict) -> bytes:
    # Sorted keys + no whitespace => stable hash for dedupe/integrity across clients
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def encrypt(data: bytes) -> bytes:
    return _fernet.encrypt(data)


def decrypt(token: bytes) -> bytes:
    return _fernet.decrypt(token)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
