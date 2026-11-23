"""HMAC-SHA256 signing for webhook bodies."""

from __future__ import annotations

import hashlib
import hmac

SIGNATURE_HEADER = "X-Hookrelay-Signature"


def _key(secret: str | bytes) -> bytes:
    return secret.encode() if isinstance(secret, str) else secret


def sign(secret: str | bytes, body: bytes) -> str:
    """Return the hex HMAC-SHA256 of ``body``."""
    return hmac.new(_key(secret), body, hashlib.sha256).hexdigest()


def verify(secret: str | bytes, body: bytes, signature: str) -> bool:
    return sign(secret, body) == signature
