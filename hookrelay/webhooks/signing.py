"""HMAC-SHA256 signing for webhook bodies.

Signatures look like ``t=1700000000,v1=<hex>`` where the MAC covers
``"<t>.<body>"``, so a captured request cannot be replayed outside the
tolerance window.
"""

from __future__ import annotations

import hashlib
import hmac
import time

SIGNATURE_HEADER = "X-Hookrelay-Signature"
DEFAULT_TOLERANCE_SEC = 300


def _key(secret: str | bytes) -> bytes:
    return secret.encode() if isinstance(secret, str) else secret


def _digest(secret: str | bytes, message: bytes) -> str:
    return hmac.new(_key(secret), message, hashlib.sha256).hexdigest()


def _equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def sign(secret: str | bytes, body: bytes, timestamp: float | None = None) -> str:
    """Return a ``t=...,v1=...`` signature for ``body``."""
    ts = int(time.time() if timestamp is None else timestamp)
    return f"t={ts},v1={_digest(secret, f'{ts}.'.encode() + body)}"


def sign_legacy(secret: str | bytes, body: bytes) -> str:
    """Bare hex MAC of the body, as emitted before 0.2.0."""
    return _digest(secret, body)


def _parse(signature: str) -> tuple[int, str] | None:
    fields: dict[str, str] = {}
    for part in signature.split(","):
        key, sep, value = part.partition("=")
        if not sep:
            return None
        fields[key.strip()] = value.strip()
    try:
        return int(fields["t"]), fields["v1"]
    except (KeyError, ValueError):
        return None


def verify(
    secret: str | bytes,
    body: bytes,
    signature: str,
    *,
    now: float | None = None,
    tolerance_sec: float = DEFAULT_TOLERANCE_SEC,
) -> bool:
    # Back-compat: a bare hex digest is the pre-0.2.0 format. Accepted for one
    # release so receivers can upgrade before senders; remove in 0.3.0.
    if "=" not in signature:
        return _equal(sign_legacy(secret, body), signature)

    parsed = _parse(signature)
    if parsed is None:
        return False
    ts, v1 = parsed
    current = time.time() if now is None else now
    if abs(current - ts) > tolerance_sec:
        return False
    return _equal(_digest(secret, f"{ts}.".encode() + body), v1)
