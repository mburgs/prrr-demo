"""Runtime settings."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, Mapping


@dataclass(frozen=True)
class Settings:
    webhook_url: str = "https://hooks.example.com/ingest"
    secret: str = "dev-secret"
    # Total delivery attempts per event, including the first one.
    retry_count: int = 3
    retry_delay_sec: float = 0.5
    timeout_sec: float = 5.0
    bucket_capacity: int = 10
    bucket_refill_per_sec: float = 5.0

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Settings":
        known = {f.name for f in fields(cls)}
        unknown = sorted(set(data) - known)
        if unknown:
            raise ValueError(f"unknown settings: {', '.join(unknown)}")
        return cls(**data)
