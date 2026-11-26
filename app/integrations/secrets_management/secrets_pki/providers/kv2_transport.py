from __future__ import annotations

import os
from urllib.parse import urlsplit


def validate_secret_endpoint(value: str, *, allowed_origins_env: str, provider_label: str) -> str:
    """Fail closed on HTTP, user-info, redirects and unapproved origins."""
    value = str(value or '').strip()
    try:
        url = urlsplit(value)
        port = url.port
    except ValueError as exc:
        raise ValueError(f'{provider_label} endpoint is invalid.') from exc
    if (
        url.scheme != 'https'
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in {'', '/'}
    ):
        raise ValueError(f'{provider_label} requires an HTTPS origin without path, query or credentials.')
    host = url.hostname.lower().rstrip('.')
    if not host or '%' in host or '\\' in value:
        raise ValueError(f'Invalid {provider_label} endpoint host.')
    origin = f'https://{host}' + (f':{port}' if port is not None and port != 443 else '')
    allowed = set()
    for entry in os.getenv(allowed_origins_env, '').split(','):
        raw = entry.strip()
        if not raw:
            continue
        parsed = urlsplit(raw)
        try:
            parsed_port = parsed.port
        except ValueError:
            continue
        if (
            parsed.scheme == 'https'
            and parsed.hostname
            and not parsed.path.strip('/')
            and not parsed.query
            and not parsed.fragment
            and not parsed.username
        ):
            h = parsed.hostname.lower().rstrip('.')
            allowed.add(f'https://{h}' + (f':{parsed_port}' if parsed_port is not None and parsed_port != 443 else ''))
    if origin not in allowed:
        raise ValueError(f'{provider_label} HTTPS origin is not approved by {allowed_origins_env}.')
    return origin


def validate_auth_mount(value: str) -> str:
    """Only an approved single mount segment; never arbitrary API paths."""
    mount = str(value or '').strip('/')
    if not mount or len(mount) > 160 or not all(c.isascii() and (c.isalnum() or c in '-_') for c in mount):
        raise ValueError('AppRole auth mount must be one safe path segment.')
    return mount
