from __future__ import annotations

import re

RAW_ERROR_PATTERNS = (
    'traceback (most recent call last)',
    'httpconnectionpool(',
    'httpsconnectionpool(',
    'max retries exceeded',
    'newconnectionerror',
    'failed to establish a new connection',
    'connection refused',
    'connection aborted',
    'apiexception',
    'status reason headers body',
    'sqlalchemy.exc.',
    'integrityerror',
    'operationalerror',
    'programmingerror',
    'notfoundexception',
    'exception:',
)

_TITLE_CASE_OVERRIDES = {
    'api': 'API',
    'configmap': 'ConfigMap',
    'csv': 'CSV',
    'http': 'HTTP',
    'https': 'HTTPS',
    'id': 'ID',
    'jit': 'JIT',
    'kaori': 'KAORI',
    'k8s': 'K8s',
    'ldap': 'LDAP',
    'minio': 'MinIO',
    'oidc': 'OIDC',
    'rbac': 'RBAC',
    's3': 'S3',
    'saml': 'SAML',
    'sso': 'SSO',
    'tls': 'TLS',
    'url': 'URL',
}


def standardize_activity_title(value: str | None) -> str | None:
    """Return a compact Title Case label while preserving KAORI acronyms."""
    if value is None:
        return None
    normalized = re.sub(r'\s+', ' ', str(value)).strip()
    if not normalized:
        return None

    def _word(match: re.Match[str]) -> str:
        token = match.group(0)
        override = _TITLE_CASE_OVERRIDES.get(token.lower())
        if override is not None:
            return override
        return token[:1].upper() + token[1:].lower()

    return re.sub(r'[A-Za-z0-9]+', _word, normalized)


def activity_failure_message(event_type: str, text: str) -> str:
    normalized = text.lower()

    if any(token in normalized for token in ('timeout', 'timed out', 'read timed out')):
        return 'The operation timed out before the target service responded. Review service availability, network access, and the configured timeout.'
    if any(token in normalized for token in ('certificate', 'ssl', 'tls', 'x509')):
        return 'The secure connection could not be verified. Review the endpoint certificate and TLS verification settings.'
    if any(token in normalized for token in ('401', 'unauthorized', 'authentication failed', 'invalid credential')):
        return (
            'The target service rejected the configured credentials. Review the authentication settings and try again.'
        )
    if any(token in normalized for token in ('403', 'forbidden', 'permission denied')):
        return 'The configured account does not have permission to complete this operation. Review the assigned access and credentials.'
    if any(token in normalized for token in ('404', 'not found', 'notfound')):
        return (
            'The requested endpoint or resource was not found. Review the configured address and resource availability.'
        )
    if any(
        token in normalized
        for token in (
            'connection refused',
            'max retries exceeded',
            'connectionerror',
            'httpconnectionpool',
            'httpsconnectionpool',
        )
    ):
        return 'KAORI could not reach the configured endpoint. Review the endpoint, network route, service availability, and firewall access.'
    if any(token in normalized for token in ('integrityerror', 'operationalerror', 'sqlalchemy', 'database')):
        return 'KAORI could not complete the database operation. Review database availability and KAORI logs before retrying.'
    if 'kubernetes' in event_type or event_type.startswith('cluster_'):
        return 'The Kubernetes operation could not be completed. Review API reachability, kubeconfig credentials, TLS settings, and cluster compatibility.'
    if event_type.startswith('prometheus_'):
        return 'The Prometheus operation could not be completed. Review the endpoint, authentication, TLS settings, and service availability.'
    if event_type.startswith('alertmanager_'):
        return 'The Alertmanager operation could not be completed. Review the endpoint, authentication, TLS settings, and service availability.'
    if event_type.startswith('operational_activity_'):
        return 'The activity retention operation could not be completed safely. Review the retention status and worker logs before retrying.'

    return 'The operation could not be completed. Review the related configuration and KAORI logs, then try again.'


def standardize_activity_text(
    value: str | None,
    *,
    event_type: str,
    status: str,
) -> str | None:
    if value is None:
        return None

    normalized = re.sub(r'\s+', ' ', str(value)).strip()
    if not normalized:
        return None

    lowered = normalized.lower()
    looks_raw = (
        any(pattern in lowered for pattern in RAW_ERROR_PATTERNS)
        or normalized.startswith(('{', '[', '<'))
        or '\\n' in normalized
        or len(normalized) > 700
    )

    if status in {'error', 'warning'} and looks_raw:
        return activity_failure_message(event_type, normalized)

    return normalized
