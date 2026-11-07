import base64
import binascii
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import settings


def hash_password(password: str, *, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 390_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, expected = encoded.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    actual = hash_password(password, salt=salt).split("$", 2)[2]
    return hmac.compare_digest(actual, expected)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_session(actor_id: str, actor_type: str, csrf_token: str, ttl_hours: int = 12) -> str:
    payload = {
        "sub": actor_id,
        "type": actor_type,
        "csrf": csrf_token,
        "exp": int((datetime.now(UTC) + timedelta(hours=ttl_hours)).timestamp()),
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = hmac.new(settings.session_secret.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64encode(signature)}"


def decode_session(token: str) -> dict[str, Any] | None:
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(
            settings.session_secret.encode(), body.encode(), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _b64decode(signature)):
            return None
        payload = json.loads(_b64decode(body))
        if not isinstance(payload, dict) or payload["exp"] < int(datetime.now(UTC).timestamp()):
            return None
        if not all(isinstance(payload.get(key), str) for key in ("sub", "type", "csrf")):
            return None
        return payload
    except (ValueError, KeyError, json.JSONDecodeError, binascii.Error):
        return None


def mask_phone(phone: str) -> str:
    if len(phone) < 7:
        return "***"
    return f"{phone[:3]}****{phone[-4:]}"
