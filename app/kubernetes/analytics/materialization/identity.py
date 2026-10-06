from __future__ import annotations

from hashlib import sha256
from typing import Any


def normalize_parameters(parameters: dict[str, Any] | None) -> dict[str, str]:
    """Return the canonical ordered parameter mapping used for snapshot identity."""
    return {
        str(key): str(value)
        for key, value in sorted((parameters or {}).items())
        if value is not None and str(value).strip() != ''
    }


def parameter_fingerprint(parameters: dict[str, Any] | None) -> str:
    """Return the stable SHA-256 fingerprint for canonical snapshot parameters."""
    normalized = normalize_parameters(parameters)
    payload = '&'.join(f'{key}={value}' for key, value in normalized.items())
    return sha256(payload.encode('utf-8')).hexdigest()
