import base64
import hashlib
import hmac
import json
import time

from app import settings


def issue_token(id_number: str, ttl_seconds: int = 600) -> str:
    payload = {"sub": id_number, "exp": int(time.time()) + ttl_seconds}
    body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    sig = hmac.new(
        settings.SECRET_KEY.encode(), body.encode(), hashlib.sha256
    ).hexdigest()
    return f"{body}.{sig}"


def verify_token(token: str, id_number: str) -> bool:
    try:
        body, sig = token.split(".", 1)
    except ValueError:
        return False
    expected = hmac.new(
        settings.SECRET_KEY.encode(), body.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return False
    try:
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
    except Exception:
        return False
    return payload.get("sub") == id_number and int(payload.get("exp", 0)) >= int(time.time())


def hash_code(id_number: str, phone: str, code: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(),
        f"{id_number}:{phone}:{code}".encode(),
        hashlib.sha256,
    ).hexdigest()
