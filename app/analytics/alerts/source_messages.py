from __future__ import annotations

from typing import Any

_TIMEOUT_MARKERS = (
    'timed out',
    'timeout',
    'max retries exceeded',
    'connection refused',
    'connection reset',
    'connection aborted',
    'connecttimeout',
    'readtimeout',
    'name or service not known',
    'temporary failure in name resolution',
    'nodename nor servname provided',
    'network is unreachable',
    'no route to host',
    'failed to establish a new connection',
)
_AUTH_MARKERS = (
    '401',
    '403',
    'unauthorized',
    'forbidden',
    'authentication',
    'invalid token',
    'access denied',
)
_TLS_MARKERS = (
    'certificate verify failed',
    'sslerror',
    'tls',
    'x509',
    'certificate has expired',
    'self signed certificate',
)
_CONFIGURATION_MARKERS = (
    'not configured',
    'no enabled',
    'no binding',
    'binding is unavailable',
    'endpoint is required',
    'instance is unavailable',
)


def _text(value: Any) -> str:
    return str(value or '').strip()


def friendly_alert_source_error(
    value: Any,
    *,
    source_label: str,
) -> str:
    """Convert provider/HTTP exceptions into concise operator-facing guidance.

    Raw exception text belongs in server logs and runtime observations, not in UI
    snapshots where it can expose endpoints, query strings, and client internals.
    """
    raw = _text(value)
    lowered = raw.lower()
    if any(marker in lowered for marker in _CONFIGURATION_MARKERS):
        return f'{source_label} is not configured for this cluster.'
    if any(marker in lowered for marker in _AUTH_MARKERS):
        return f'{source_label} rejected KAORI authentication. Review the configured credentials.'
    if any(marker in lowered for marker in _TLS_MARKERS):
        return f'{source_label} TLS verification failed. Review the endpoint certificate and trust settings.'
    if any(marker in lowered for marker in _TIMEOUT_MARKERS):
        return f'{source_label} is temporarily unreachable. KAORI will retry automatically.'
    return f'{source_label} is temporarily unavailable. KAORI will retry automatically.'


def friendly_alert_fallback_reason(*, primary_available: bool, fallback_available: bool) -> str | None:
    if primary_available:
        return None
    if fallback_available:
        return 'Alertmanager is unavailable, so KAORI is using the Prometheus ALERTS fallback.'
    return 'Alertmanager and the Prometheus ALERTS fallback are currently unavailable.'


def friendly_combined_alert_error() -> str:
    return (
        'Alert data is temporarily unavailable because neither Alertmanager nor the '
        'Prometheus fallback could be reached. KAORI will retry automatically.'
    )
