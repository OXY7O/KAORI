from __future__ import annotations

import re
from typing import Any

from app.notifications.normalization import standardize_activity_text


def changed_fields(metadata: dict[str, Any]) -> list[dict[str, str]]:
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
        if not value:
            return '-'
        return ', '.join(
            f'{str(key).replace("_", " ").title()}: {_metadata_value(item)}' for key, item in value.items()
        )
    if isinstance(value, list):
        return ', '.join(_metadata_value(item) for item in value) if value else '-'
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if value is None:
        return '-'
    return re.sub(r'\s+', ' ', str(value)).strip() or '-'


def metadata_items(
    metadata: dict[str, Any],
    *,
    event_type: str,
) -> list[dict[str, Any]]:
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
        if key.startswith('previous_') or key in context_keys:
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
