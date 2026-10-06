from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def safe_endpoint(value: str | None) -> str:
    """Return an endpoint safe for presentation and operator console links."""
    if not value:
        return 'Not configured'
    parsed = urlsplit(value)
    host = parsed.hostname or 'configured endpoint'
    if ':' in host and not host.startswith('['):
        host = f'[{host}]'
    port = f':{parsed.port}' if parsed.port else ''
    path = parsed.path.rstrip('/')
    return urlunsplit((parsed.scheme or 'http', f'{host}{port}', path, '', ''))
