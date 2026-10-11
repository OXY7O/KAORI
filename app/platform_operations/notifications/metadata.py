from __future__ import annotations

import re
from typing import Any

from app.platform_operations.notifications.normalization import standardize_activity_text

_SENSITIVE_METADATA_TOKENS = (
    'password',
    'passwd',
    'passphrase',
    'secret',
    'token',
    'private_key',
    'privatekey',
    'kubeconfig',
    'credential_value',
    'authorization',
    'cookie',
    'client_assertion',
    'api_key',
    'apikey',
    'access_key',
    'session_key',
    'private_material',
)
# Only known non-secret references are exempt. Generic *_ref / *_id suffixes
# are not trusted because a producer could mislabel an actual credential.
_SAFE_SENSITIVE_KEYS = frozenset({
    'secret_name',
    'secret_id',
    'secret_ref',
    'secret_reference',
    'credential_owner',
    'credential_id',
    'credential_ref',
    'credential_reference',
    'credential_name',
    'token_id',
    'token_ref',
    'token_name',
    'access_token_id',
    'certificate_id',
    'kubeconfig_name',
    'secret_recorded',
    'secret_env',
    'secret_env_var',
})
_MAX_METADATA_DEPTH = 12
_MAX_METADATA_ENTRIES = 500
_MAX_METADATA_TEXT = 4096
_REDACTED = '[REDACTED]'

_URL_CREDENTIAL = re.compile(r'(?i)(https?://)[^/@\s]+:[^/@\s]+@')
_AUTHORIZATION_VALUE = re.compile(r'(?i)\b(bearer|basic)\s+[a-z0-9._~+/\-]+=*')
_SENSITIVE_ASSIGNMENT = re.compile(
    r'''(?i)(["']?(?:password|passwd|passphrase|token|access[-_]?token|refresh[-_]?token|secret|client[-_]?secret|(?:x[-_])?api[-_]?key|apikey|authorization|cookie|session[-_]?key|private[-_]?key|kubeconfig)["']?\s*[:=]\s*)(["']?)([^\s,'";&}\]]+)'''
)
_PRIVATE_KEY_MARKER = re.compile(r'(?i)-----BEGIN\s+(?:[A-Z ]*\s)?PRIVATE KEY-----')
_CONTROL_CHARACTERS = re.compile(r'[\x00-\x08\x0b-\x1f\x7f]')


def _sensitive_metadata_key(key: str) -> bool:
    normalized = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', str(key)).strip().lower()
    normalized = re.sub(r'[^a-z0-9]+', '_', normalized).strip('_')
    if normalized in _SAFE_SENSITIVE_KEYS:
        return False
    collapsed = normalized.replace('_', '')
    return any(token.replace('_', '') in collapsed for token in _SENSITIVE_METADATA_TOKENS)


def redact_operational_text(value: object, *, limit: int = _MAX_METADATA_TEXT) -> str:
    """Conservatively remove credential-shaped material from operational evidence strings."""
    from urllib.parse import unquote

    rendered = str(value or '')
    # Decode only when encoded credential markers are present. Decoding all
    # evidence would change legitimate percent-encoded action URLs/references.
    encoded_secret = re.search(
        r'(?i)(?:password|passwd|passphrase|token|secret|api[_-]?key|client_secret|authorization|cookie)(?:%(?:25)?3[da])',
        rendered,
    ) or re.search(r'(?i)https?%3a%2f%2f', rendered)
    if encoded_secret:
        for _ in range(2):
            decoded = unquote(rendered)
            if decoded == rendered:
                break
            rendered = decoded
    rendered = _CONTROL_CHARACTERS.sub(' ', rendered)
    if _PRIVATE_KEY_MARKER.search(rendered):
        return _REDACTED
    rendered = _URL_CREDENTIAL.sub(r'\1***:***@', rendered)
    rendered = _AUTHORIZATION_VALUE.sub(r'\1 [REDACTED]', rendered)
    rendered = _SENSITIVE_ASSIGNMENT.sub(lambda match: match.group(1) + _REDACTED, rendered)
    rendered = re.sub(r'\s+', ' ', rendered).strip()
    cap = max(16, min(limit, 8192))
    return rendered[:cap] if len(rendered) > cap else rendered


def _redact_operational_value(value: Any, *, depth: int = 0) -> Any:
    if depth >= _MAX_METADATA_DEPTH:
        return _REDACTED
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in list(value.items())[:_MAX_METADATA_ENTRIES]:
            name = str(key)
            if _sensitive_metadata_key(name):
                continue
            result[name] = _redact_operational_value(child, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [_redact_operational_value(child, depth=depth + 1) for child in value[:_MAX_METADATA_ENTRIES]]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return redact_operational_text(value)


def redact_operational_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    """One non-mutating, nested-safe projection for persistence, display and archival."""
    if metadata is None:
        return None
    return _redact_operational_value(metadata)


def changed_fields(metadata: dict[str, Any]) -> list[dict[str, str]]:
    metadata = redact_operational_metadata(metadata) or {}
    changed_items: list[dict[str, str]] = []
    label_overrides = {
        'name': 'Name',
        'environment': 'Environment',
        'verify_ssl': 'TLS verification',
        'allow_weak_tls': 'Allow weak TLS',
        'cluster_scope': 'Cluster scope',
        'collected_count': 'Collected TLS Secrets',
        'failed_cluster_count': 'Clusters requiring review',
    }

    for key, previous_value in metadata.items():
        if not key.startswith('previous_'):
            continue

        base_key = key.removeprefix('previous_')
        if _sensitive_metadata_key(base_key):
            continue

        current_candidates = [base_key, f'submitted_{base_key}']
        if base_key == 'name':
            current_candidates.insert(0, 'cluster_name')

        current_value = next(
            (metadata[candidate] for candidate in current_candidates if candidate in metadata),
            None,
        )

        if current_value is None or _metadata_value(previous_value) == _metadata_value(current_value):
            continue

        changed_items.append(
            {
                'label': label_overrides.get(
                    base_key,
                    base_key.replace('_', ' ').title(),
                ),
                'before': _metadata_value(previous_value),
                'after': _metadata_value(current_value),
            }
        )

    return changed_items


def _metadata_value(value: Any) -> str:
    if isinstance(value, dict):
        cleaned = redact_operational_metadata(value) or {}
        if not cleaned:
            return '-'
        return ', '.join(
            f'{str(key).replace("_", " ").title()}: {_metadata_value(item)}' for key, item in cleaned.items()
        )
    if isinstance(value, list):
        return ', '.join(_metadata_value(item) for item in value) if value else '-'
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if value is None:
        return '-'
    return redact_operational_text(value) or '-'


def metadata_items(
    metadata: dict[str, Any],
    *,
    event_type: str,
) -> list[dict[str, Any]]:
    metadata = redact_operational_metadata(metadata) or {}
    preferred_order = (
        'event_key',
        'preference',
        'security_action',
        'credential_owner',
        'timezone_mode',
        'timezone',
        'locale',
        'date_format',
        'time_format',
        'task_id',
        'archive_id',
        'certificate_id',
        'bulk_job_id',
        'cluster_scope',
        'namespace',
        'secret_name',
        'target_count',
        'validation_result',
        'uncovered_host_count',
        'updated_count',
        'operation_mode',
        'domain',
        'total_count',
        'synced_count',
        'failed_count',
        'record_count',
        'cleanup_deleted_count',
        'failed_clusters',
        'duration_seconds',
        'response_time_ms',
        'version',
        'endpoint',
        'server',
        'auth_type',
        'result',
        'result_reason',
        'reason_code',
        'ip_address',
        'browser',
        'operating_system',
        'device_type',
        'user_agent',
        'timeout_seconds',
        'verify_ssl',
        'failure_code',
        'reason',
    )
    label_overrides = {
        'event_key': 'Event key',
        'preference': 'Preference',
        'security_action': 'Security action',
        'credential_owner': 'Credential owner',
        'timezone_mode': 'Timezone source',
        'timezone': 'Timezone',
        'locale': 'Regional locale',
        'date_format': 'Date format',
        'time_format': 'Time format',
        'task_id': 'Task ID',
        'archive_id': 'Archive ID',
        'certificate_id': 'Certificate ID',
        'bulk_job_id': 'Bulk job ID',
        'cluster_scope': 'Cluster scope',
        'namespace': 'Namespace',
        'secret_name': 'TLS Secret',
        'target_count': 'Selected TLS Secrets',
        'validation_result': 'Validation result',
        'uncovered_host_count': 'Uncovered hosts',
        'updated_count': 'Updated TLS Secrets',
        'failed_targets': 'Failed TLS Secrets',
        'new_common_name': 'New Common Name',
        'new_expiry': 'New expiry',
        'cluster_id': 'Cluster ID',
        'operation_mode': 'Operation mode',
        'total_count': 'Total resources',
        'synced_count': 'Synchronized',
        'failed_count': 'Failed',
        'record_count': 'Archived records',
        'cleanup_deleted_count': 'Cleaned records',
        'duration_seconds': 'Duration',
        'response_time_ms': 'Response time',
        'timeout_seconds': 'Request timeout',
        'verify_ssl': 'TLS verification',
        'failure_code': 'Failure category',
        'reason': 'Failure summary',
        'storage_backend': 'Storage backend',
        'checksum_sha256': 'SHA-256 checksum',
        'size_bytes': 'Archive size',
        'download_kind': 'Downloaded file',
        'result': 'Authentication result',
        'result_reason': 'Result detail',
        'reason_code': 'Reason code',
        'ip_address': 'IP address',
        'browser': 'Browser',
        'operating_system': 'Operating system',
        'device_type': 'Device type',
        'user_agent': 'User agent',
    }
    context_keys = {
        'cluster_name',
        'environment',
        'submitted_name',
        'submitted_environment',
        'audit_schema',
        'access_action',
        'username',
        'auth_source',
        'authentication_provider',
        'actor_display_name',
        'actor_email',
        'actor_role',
    }

    visible_metadata: dict[str, Any] = {'event_key': event_type}
    for key, value in metadata.items():
        if key.startswith('previous_') or key in context_keys or _sensitive_metadata_key(key):
            continue
        if key.startswith('submitted_') and key.removeprefix('submitted_') in metadata:
            continue
        visible_metadata[key] = value

    keys = [key for key in preferred_order if key in visible_metadata]
    keys.extend(sorted(key for key in visible_metadata if key not in preferred_order))

    items: list[dict[str, Any]] = []
    for key in keys:
        value = visible_metadata[key]
        if key in {'reason', 'error', 'error_message'}:
            rendered_value = (
                standardize_activity_text(
                    _metadata_value(value),
                    event_type=event_type,
                    status='error',
                )
                or 'The operation did not complete successfully.'
            )
        elif key == 'duration_seconds':
            rendered_value = f'{_metadata_value(value)} seconds'
        elif key == 'response_time_ms':
            rendered_value = f'{_metadata_value(value)} ms'
        elif key == 'timeout_seconds':
            rendered_value = f'{_metadata_value(value)} seconds'
        elif key == 'size_bytes':
            try:
                size_value = int(value)
                rendered_value = (
                    f'{size_value / 1024:.1f} KiB'
                    if size_value < 1024 * 1024
                    else f'{size_value / (1024 * 1024):.1f} MiB'
                )
            except (TypeError, ValueError):
                rendered_value = _metadata_value(value)
        else:
            rendered_value = _metadata_value(value)

        is_identifier = key.endswith('_id') or key in {'event_key', 'task_id', 'checksum_sha256'}
        is_error_metadata = key in {
            'failed_count',
            'failure_code',
            'reason',
            'error',
            'error_message',
        } or (key == 'reason_code' and str(value or '').strip().lower() not in {'success', 'user_initiated'})
        items.append(
            {
                'key': key,
                'label': label_overrides.get(key, key.replace('_', ' ').title()),
                'value': rendered_value,
                'is_identifier': is_identifier,
                'tone': 'rose' if is_error_metadata else 'slate',
            }
        )

    return items
