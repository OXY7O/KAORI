"""Fail-closed Harbor outbound origin policy; provider adapter remains authoritative."""

from __future__ import annotations

import os
from urllib.parse import urlsplit


def canonical_harbor_origin(value: str) -> str | None:
    """Normalize an HTTPS origin without URL credentials, paths or ambiguity."""
    if not value or value != value.strip() or any(ord(ch) <= 32 or ord(ch) == 127 for ch in value):
        return None
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != 'https' or not hostname or not hostname.isascii()
        or hostname.endswith('.') or '%' in hostname or '\\' in hostname
        or ':' in hostname or '@' in parsed.netloc
        or parsed.username is not None or parsed.password is not None
        or parsed.path not in ('', '/') or parsed.query or parsed.fragment
        or not all(part and len(part) <= 63 for part in hostname.split('.'))
    ):
        return None
    return f'https://{hostname.lower()}' + (f':{port}' if port not in (None, 443) else '')


def validate_harbor_endpoint(endpoint: str, *, verify_ssl: bool = True) -> str:
    origin = canonical_harbor_origin(endpoint)
    if origin is None:
        raise ValueError('Harbor endpoint must be a plain HTTPS origin without credentials, path or query.')
    if not verify_ssl:
        raise ValueError('Harbor TLS certificate verification is required.')
    approved = {
        normalized
        for entry in os.getenv('INTEGRATION_HARBOR_ALLOWED_ORIGINS', '').split(',')
        if (normalized := canonical_harbor_origin(entry.strip())) is not None
    }
    if origin not in approved:
        raise ValueError('Harbor HTTPS endpoint is not in the approved integration origin list.')
    return origin
