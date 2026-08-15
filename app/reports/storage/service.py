from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from time import monotonic
from typing import Any

from flask import current_app, g
from sqlalchemy import select

from app.extensions.db import db
from app.models.report import Report
from app.reports.storage.health import (
    build_local_storage_health,
    build_s3_storage_health,
    build_storage_artifact_summary,
    build_storage_retention_policy,
    build_storage_summary_cards,
)
from app.reports.storage.local import build_local_report_storage
from app.reports.storage.s3 import build_s3_report_storage
from app.reports.storage.state import (
    clear_shared_report_storage_status,
    format_storage_check_age,
    format_storage_check_source,
    get_shared_report_storage_status,
    publish_shared_report_storage_status,
)
from app.storage.base import ArtifactStorageBackend, StoredArtifact

SUPPORTED_REPORT_STORAGE_BACKENDS = {
    'local',
    's3',
}


STORAGE_WORKSPACES = {
    'overview',
    'integrity',
    'retention',
}


def normalize_storage_workspace(value: str | None) -> str:
    normalized = str(value or 'overview').strip().lower()
    return normalized if normalized in STORAGE_WORKSPACES else 'overview'


def build_storage_operations_posture(
    *,
    backend_name: str,
    backend_status: dict[str, Any],
    artifact_summary: dict[str, Any],
    readiness_monitor: dict[str, Any],
) -> dict[str, Any]:
    read_available = bool(backend_status.get('read_available', False))
    write_available = bool(backend_status.get('write_available', False))
    reachable = bool(backend_status.get('reachable', False))
    verification_required = bool(backend_status.get('write_verification_required', False))

    if write_available:
        status_label = 'Storage Ready'
        status_tone = 'normal'
        title = 'Artifact Storage Ready'
        description = (
            'The active backend is ready for report generation, downloads, scheduled execution, '
            'and retained artifact verification.'
        )
        tip_title = 'Use Strong Verification for Recovery Events'
        tip_text = (
            'Automatic readiness is intentionally lightweight. Run Verify Storage after a write failure, '
            'endpoint or credential change, or recovery from a storage outage.'
        )
    elif read_available and verification_required:
        status_label = 'Verification Required'
        status_tone = 'warning'
        title = 'Write Verification Required'
        description = (
            'Existing artifacts remain readable, but new artifact writes stay paused until '
            'strong storage verification succeeds.'
        )
        tip_title = 'Complete Strong Verification Before Resuming Writes'
        tip_text = (
            'Connectivity has recovered, but write readiness is still guarded. Use Verify Storage to '
            'confirm the write, existence, and cleanup path before retrying generation.'
        )
    elif reachable:
        status_label = 'Needs Review'
        status_tone = 'warning'
        title = 'Artifact Writes Paused'
        description = 'The active backend is reachable, but the report artifact write path is not ready.'
        tip_title = 'Review the Write Path'
        tip_text = (
            'Check bucket or directory permissions, object prefix, and backend configuration. After the '
            'write path is corrected, run Verify Storage before resuming report generation.'
        )
    else:
        status_label = 'Disconnected'
        status_tone = 'warning'
        title = 'Artifact Execution Paused'
        description = (
            'Storage-dependent generation, downloads, verification, and scheduled artifact execution '
            'remain paused until backend connectivity is restored.'
        )
        tip_title = 'Restore Connectivity First'
        tip_text = (
            'Check the endpoint or filesystem path, credentials, bucket access, and network reachability. '
            'After recovery, run Verify Storage before allowing new artifact writes.'
        )

    return {
        'status_label': status_label,
        'status_tone': status_tone,
        'title': title,
        'description': description,
        'backend_label': str(backend_status.get('label') or backend_name.upper()),
        'read_label': 'Available' if read_available else 'Paused',
        'read_tone': 'normal' if read_available else 'warning',
        'write_label': 'Ready' if write_available else 'Paused',
        'write_tone': 'normal' if write_available else 'warning',
        'verification_label': 'Required' if verification_required else 'Not Required',
        'verification_tone': 'warning' if verification_required else 'normal',
        'monitor_label': 'Automatic' if readiness_monitor.get('enabled') else 'Manual',
        'monitor_tone': 'normal' if readiness_monitor.get('enabled') else 'unknown',
        'ready_reports': int(artifact_summary.get('ready_reports', 0) or 0),
        'checked_label': str(readiness_monitor.get('checked_label') or 'Not Checked'),
        'source_label': str(readiness_monitor.get('source_label') or 'Unknown'),
        'tip_title': tip_title,
        'tip_text': tip_text,
    }


def build_storage_integrity_presentation(result: dict[str, Any]) -> dict[str, Any]:
    presented = dict(result or {})
    samples: list[dict[str, Any]] = []
    for item in list(presented.get('missing_samples') or []):
        samples.append(
            {
                'report_id': item.get('report_id'),
                'name': item.get('name') or 'Generated Report',
                'backend': item.get('backend') or 'Unknown',
                'reference': item.get('file_path') or 'Not Available',
                'issue': 'Artifact reference is missing from the configured backend.',
                'tone': 'critical',
                'status': 'Missing',
            }
        )
    for item in list(presented.get('error_samples') or []):
        samples.append(
            {
                'report_id': item.get('report_id'),
                'name': item.get('name') or 'Generated Report',
                'backend': item.get('backend') or 'Unknown',
                'reference': item.get('file_path') or 'Not Available',
                'issue': item.get('error') or 'Storage verification returned an error.',
                'tone': 'warning',
                'status': 'Error',
            }
        )
    presented['review_samples'] = samples
    return presented


_STORAGE_STATUS_CACHE_KEY = '_kaori_report_storage_status'
_PROCESS_STORAGE_STATUS_CACHE: dict[tuple[object, ...], tuple[float, dict[str, Any]]] = {}
_PROCESS_STORAGE_STATUS_CACHE_LOCK = Lock()


class ReportStorageUnavailable(RuntimeError):
    """Raised when a configured artifact backend cannot be reached safely."""


def _format_storage_backend_label(backend_name: str) -> str:
    normalized = str(backend_name or '').lower().strip()
    if normalized == 's3':
        return 'S3-compatible storage'
    if normalized == 'local':
        return 'Local filesystem'
    return 'Report storage'


def _get_storage_status_cache_ttl_seconds() -> int:
    try:
        value = int(current_app.config.get('REPORT_STORAGE_STATUS_CACHE_SECONDS', 15) or 15)
    except (TypeError, ValueError):
        value = 15
    return max(0, min(value, 300))


def _get_process_storage_status_cache_key(backend_name: str) -> tuple[object, ...]:
    app_identity = id(current_app.config)
    if backend_name == 's3':
        return (
            app_identity,
            backend_name,
            str(current_app.config.get('REPORT_S3_BUCKET', '') or ''),
            str(current_app.config.get('REPORT_S3_ENDPOINT_URL', '') or ''),
            str(current_app.config.get('REPORT_S3_REGION', '') or ''),
            str(current_app.config.get('REPORT_S3_PREFIX', '') or ''),
        )
    return (
        app_identity,
        backend_name,
        str(current_app.config.get('REPORT_LOCAL_STORAGE_DIR', '') or ''),
    )


def _get_process_cached_storage_status(backend_name: str) -> dict[str, Any] | None:
    ttl_seconds = _get_storage_status_cache_ttl_seconds()
    if ttl_seconds <= 0:
        return None
    cache_key = _get_process_storage_status_cache_key(backend_name)
    with _PROCESS_STORAGE_STATUS_CACHE_LOCK:
        cached = _PROCESS_STORAGE_STATUS_CACHE.get(cache_key)
        if cached is None:
            return None
        expires_at, status = cached
        if expires_at <= monotonic():
            _PROCESS_STORAGE_STATUS_CACHE.pop(cache_key, None)
            return None
        return dict(status)


def _set_process_cached_storage_status(backend_name: str, status: dict[str, Any]) -> None:
    ttl_seconds = _get_storage_status_cache_ttl_seconds()
    if ttl_seconds <= 0:
        return
    cache_key = _get_process_storage_status_cache_key(backend_name)
    with _PROCESS_STORAGE_STATUS_CACHE_LOCK:
        _PROCESS_STORAGE_STATUS_CACHE[cache_key] = (monotonic() + ttl_seconds, dict(status))


def _clear_process_storage_status_cache() -> None:
    app_id = id(current_app.config)
    with _PROCESS_STORAGE_STATUS_CACHE_LOCK:
        for cache_key in list(_PROCESS_STORAGE_STATUS_CACHE):
            if cache_key and cache_key[0] == app_id:
                _PROCESS_STORAGE_STATUS_CACHE.pop(cache_key, None)


def _get_storage_status_cache() -> dict[str, dict[str, Any]]:
    cache = getattr(g, _STORAGE_STATUS_CACHE_KEY, None)
    if cache is None:
        cache = {}
        setattr(g, _STORAGE_STATUS_CACHE_KEY, cache)
    return cache


def clear_report_storage_status_cache(*, include_shared: bool = False) -> None:
    """Clear local readiness caches before an explicit retry.

    Shared Redis state is preserved by default so one web process cannot erase
    the canonical multi-process snapshot. Pass ``include_shared=True`` only
    when configuration changed and the shared snapshot must be invalidated.
    """

    setattr(g, _STORAGE_STATUS_CACHE_KEY, {})
    _clear_process_storage_status_cache()
    if include_shared:
        clear_shared_report_storage_status(get_configured_storage_backend_name())


def _cache_storage_status(
    backend_name: str,
    status: dict[str, Any],
    *,
    source: str = 'direct',
) -> dict[str, Any]:
    published = publish_shared_report_storage_status(status, source=source)
    _get_storage_status_cache()[backend_name] = published
    _set_process_cached_storage_status(backend_name, published)
    return published


def get_report_storage_backend_status(
    backend_name: str | None = None,
    *,
    force: bool = False,
    source: str = 'direct',
) -> dict[str, Any]:
    """Return a sanitized, request-cached readiness state for one backend.

    External connection errors are logged but never exposed to templates. The
    result is reusable by overview, generate, schedules, storage, and generated
    report pages so they all degrade in the same way.
    """

    normalized_backend = str(backend_name or get_configured_storage_backend_name()).lower().strip()
    if normalized_backend not in SUPPORTED_REPORT_STORAGE_BACKENDS:
        return _cache_storage_status(
            normalized_backend,
            {
                'backend': normalized_backend or 'unknown',
                'label': _format_storage_backend_label(normalized_backend),
                'configured': False,
                'reachable': False,
                'available': False,
                'read_available': False,
                'write_available': False,
                'state': 'unsupported',
                'status': 'Needs Review',
                'tone': 'amber',
                'icon': 'circle-alert',
                'title': 'Storage Configuration Needs Review',
                'description': 'The configured report storage backend is not supported.',
                'action_label': 'Review Storage',
            },
            source=source,
        )

    cache = _get_storage_status_cache()
    if not force and normalized_backend in cache:
        return cache[normalized_backend]
    if not force:
        shared_status = get_shared_report_storage_status(normalized_backend)
        if shared_status is not None:
            cache[normalized_backend] = shared_status
            _set_process_cached_storage_status(normalized_backend, shared_status)
            return shared_status
        process_cached = _get_process_cached_storage_status(normalized_backend)
        if process_cached is not None:
            cache[normalized_backend] = process_cached
            return process_cached

    previous_shared_status = (
        get_shared_report_storage_status(normalized_backend, allow_stale=True) if normalized_backend == 's3' else None
    )

    if normalized_backend == 'local':
        health = build_local_storage_health()
        readable = bool(health.get('root_exists', False))
        writable = bool(health.get('root_writable', False))
        available = readable and writable
        return _cache_storage_status(
            normalized_backend,
            {
                'backend': 'local',
                'label': 'Local filesystem',
                'configured': True,
                'reachable': readable,
                'available': available,
                'read_available': readable,
                'write_available': writable,
                'state': 'ready' if available else 'unavailable',
                'status': 'Connected' if available else 'Needs Review',
                'tone': 'green' if available else 'amber',
                'icon': 'hard-drive' if available else 'circle-alert',
                'title': 'Local Report Storage Is Ready' if available else 'Local Report Storage Needs Review',
                'description': (
                    'The local report storage path is writable.'
                    if available
                    else 'KAORI cannot write to the configured local report storage path. Existing report records remain available.'
                ),
                'action_label': 'Review Storage',
            },
            source=source,
        )

    health = build_s3_storage_health()
    configured = bool(health.get('configuration_complete', False))
    if not configured:
        return _cache_storage_status(
            normalized_backend,
            {
                'backend': 's3',
                'label': 'S3-compatible storage',
                'configured': False,
                'reachable': False,
                'available': False,
                'read_available': False,
                'write_available': False,
                'state': 'misconfigured',
                'status': 'Needs Review',
                'tone': 'amber',
                'icon': 'cloud-off',
                'title': 'S3 Storage Configuration Is Incomplete',
                'description': (
                    'KAORI will keep report pages available, but generation and download actions remain paused until the bucket and S3 dependency are configured.'
                ),
                'action_label': 'Review Storage',
            },
            source=source,
        )

    try:
        backend = build_report_storage_backend('s3')
        test_connection = getattr(backend, 'test_connection', None)
        if callable(test_connection):
            test_connection()
    except Exception:
        current_app.logger.warning(
            'S3-compatible report storage is configured but unreachable.',
            exc_info=True,
        )
        return _cache_storage_status(
            normalized_backend,
            {
                'backend': 's3',
                'label': 'S3-compatible storage',
                'configured': True,
                'reachable': False,
                'available': False,
                'read_available': False,
                'write_available': False,
                'state': 'unavailable',
                'status': 'Disconnected',
                'tone': 'amber',
                'icon': 'cloud-off',
                'title': 'S3 Report Storage Is Temporarily Unavailable',
                'description': (
                    'KAORI could not reach the configured S3 or MinIO endpoint. Report pages and database records remain available; S3-dependent generation, verification, and downloads are paused until connectivity returns. Artifacts on other reachable backends remain usable.'
                ),
                'action_label': 'Retry Connection',
            },
            source=source,
        )

    if (
        source != 'manual_verification'
        and previous_shared_status is not None
        and bool(previous_shared_status.get('write_verification_required', False))
    ):
        return _cache_storage_status(
            normalized_backend,
            {
                'backend': 's3',
                'label': 'S3-compatible storage',
                'configured': True,
                'reachable': True,
                'available': False,
                'read_available': True,
                'write_available': False,
                'write_verification_required': True,
                'state': 'degraded',
                'status': 'Verification Required',
                'tone': 'amber',
                'icon': 'shield-alert',
                'title': 'S3 Storage Is Reachable but Write Verification Is Required',
                'description': (
                    'KAORI can reach the configured S3 or MinIO bucket, but a previous write or strong verification failure remains unresolved. '
                    'New report generation stays paused until Test Storage succeeds.'
                ),
                'action_label': 'Verify Storage',
            },
            source=source,
        )

    return _cache_storage_status(
        normalized_backend,
        {
            'backend': 's3',
            'label': 'S3-compatible storage',
            'configured': True,
            'reachable': True,
            'available': True,
            'read_available': True,
            'write_available': True,
            'write_verification_required': False,
            'state': 'ready',
            'status': 'Connected',
            'tone': 'green',
            'icon': 'cloud-check',
            'title': 'S3 Report Storage Is Connected',
            'description': 'KAORI can reach the configured S3 or MinIO bucket for report artifacts.',
            'action_label': 'Test Storage',
        },
        source=source,
    )


def refresh_report_storage_readiness(
    backend_name: str | None = None,
    *,
    source: str = 'periodic',
) -> dict[str, Any]:
    """Run a fresh lightweight probe and publish one shared readiness snapshot."""

    normalized_backend = str(backend_name or get_configured_storage_backend_name()).lower().strip()
    clear_report_storage_status_cache()
    return get_report_storage_backend_status(
        normalized_backend,
        force=True,
        source=source,
    )


def mark_report_storage_backend_unavailable(
    backend_name: str,
    *,
    source: str = 'operation_failure',
) -> dict[str, Any]:
    """Publish a sanitized unavailable state after an artifact operation fails."""

    normalized_backend = str(backend_name or 'unknown').lower().strip()
    write_verification_required = source in {
        'artifact_write_failure',
        'manual_verification_failure',
    }
    return _cache_storage_status(
        normalized_backend,
        {
            'backend': normalized_backend,
            'label': _format_storage_backend_label(normalized_backend),
            'configured': True,
            'reachable': False,
            'available': False,
            'read_available': False,
            'write_available': False,
            'write_verification_required': write_verification_required,
            'state': 'unavailable',
            'status': 'Disconnected',
            'tone': 'amber',
            'icon': 'cloud-off' if normalized_backend == 's3' else 'circle-alert',
            'title': 'Report Storage Is Temporarily Unavailable',
            'description': (
                'KAORI could not reach the artifact storage backend. Report pages and database records remain available while storage-dependent actions are paused.'
            ),
            'action_label': 'Retry Connection',
        },
        source=source,
    )


def probe_report_artifact(stored_path: str | None) -> dict[str, Any]:
    """Probe one artifact without allowing storage failures to break a page."""

    if not stored_path:
        return {
            'exists': False,
            'reachable': True,
            'backend': 'none',
            'backend_label': 'Report storage',
            'state': 'not_generated',
        }

    try:
        backend_name, object_key = parse_report_storage_uri(stored_path)
    except (TypeError, ValueError):
        return {
            'exists': False,
            'reachable': True,
            'backend': 'invalid',
            'backend_label': 'Invalid storage reference',
            'state': 'invalid',
        }

    backend_status = get_report_storage_backend_status(backend_name)
    if not bool(backend_status.get('reachable', False)):
        return {
            'exists': False,
            'reachable': False,
            'backend': backend_name,
            'backend_label': _format_storage_backend_label(backend_name),
            'state': 'unavailable',
        }

    try:
        backend = build_report_storage_backend(backend_name)
        exists = backend.exists(object_key)
    except Exception:
        current_app.logger.warning(
            'Unable to verify report artifact in %s storage.',
            backend_name,
            exc_info=True,
        )
        mark_report_storage_backend_unavailable(backend_name)
        return {
            'exists': False,
            'reachable': False,
            'backend': backend_name,
            'backend_label': _format_storage_backend_label(backend_name),
            'state': 'unavailable',
        }

    return {
        'exists': bool(exists),
        'reachable': True,
        'backend': backend_name,
        'backend_label': _format_storage_backend_label(backend_name),
        'state': 'available' if exists else 'missing',
    }


def get_configured_storage_backend_name() -> str:
    backend_name = (
        str(
            current_app.config.get(
                'REPORT_STORAGE_BACKEND',
                'local',
            )
            or 'local'
        )
        .lower()
        .strip()
    )

    if backend_name not in SUPPORTED_REPORT_STORAGE_BACKENDS:
        current_app.logger.warning(
            'Unsupported REPORT_STORAGE_BACKEND=%s. Falling back to local.',
            backend_name,
        )
        return 'local'

    return backend_name


def get_active_report_storage_backend() -> ArtifactStorageBackend:
    return build_report_storage_backend(
        get_configured_storage_backend_name(),
    )


def get_report_storage_backend_for_uri(
    stored_path: str,
) -> ArtifactStorageBackend:
    backend_name, _object_key = parse_report_storage_uri(
        stored_path,
    )

    return build_report_storage_backend(
        backend_name,
    )


def build_report_storage_backend(
    backend_name: str,
) -> ArtifactStorageBackend:
    normalized_backend = backend_name.lower().strip()

    if normalized_backend == 'local':
        return build_local_report_storage()

    if normalized_backend == 's3':
        return build_s3_report_storage()

    raise RuntimeError(
        f'Unsupported report storage backend: {backend_name}. Supported backends: local, s3.',
    )


def save_report_file(
    source_path: Path,
    object_key: str,
    *,
    content_type: str = 'application/pdf',
) -> StoredArtifact:
    backend_name = get_configured_storage_backend_name()
    backend = get_active_report_storage_backend()
    try:
        return backend.save_file(
            source_path=source_path,
            object_key=object_key,
            content_type=content_type,
        )
    except Exception:
        mark_report_storage_backend_unavailable(
            backend_name,
            source='artifact_write_failure',
        )
        raise


def build_report_download_path(
    stored_path: str,
) -> Path:
    backend_name, object_key = parse_report_storage_uri(stored_path)
    backend = build_report_storage_backend(backend_name)
    try:
        return backend.build_download_path(object_key)
    except Exception:
        mark_report_storage_backend_unavailable(
            backend_name,
            source='artifact_read_failure',
        )
        raise


def report_file_exists(
    stored_path: str,
) -> bool:
    probe = probe_report_artifact(stored_path)
    if not bool(probe.get('reachable', True)):
        raise ReportStorageUnavailable(f'{probe.get("backend_label", "Report storage")} is temporarily unavailable.')
    return bool(probe.get('exists', False))


def parse_report_storage_uri(
    stored_path: str,
) -> tuple[str, str]:
    if not stored_path:
        raise ValueError(
            'Report file path is empty.',
        )

    if ':' not in stored_path:
        raise ValueError(
            'Report storage URI must use the local:<object_key> or s3:<object_key> format.',
        )

    backend_name, object_key = stored_path.split(
        ':',
        1,
    )
    backend_name = backend_name.lower().strip()
    object_key = object_key.strip().lstrip('/')

    if backend_name not in SUPPORTED_REPORT_STORAGE_BACKENDS:
        raise ValueError(
            f'Unsupported report storage backend: {backend_name}. Supported backends: local, s3.',
        )

    if not object_key:
        raise ValueError(
            'Report storage object key is empty.',
        )

    return backend_name, object_key


def get_report_storage_payload(*, workspace: str | None = None) -> dict[str, Any]:
    backend_name = get_configured_storage_backend_name()
    local_health = build_local_storage_health()
    s3_health = build_s3_storage_health()
    artifact_summary = build_storage_artifact_summary()
    retention_policy = build_storage_retention_policy()
    backend_status = get_report_storage_backend_status(backend_name)
    summary_cards = build_storage_summary_cards(backend_name)
    if summary_cards:
        summary_cards[0] = {
            **summary_cards[0],
            'value': str(backend_status['status']),
            'caption': str(backend_status['label']),
            'icon': str(backend_status['icon']),
            'tone': str(backend_status['tone']),
        }
    lifecycle_summary = build_storage_lifecycle_summary(
        backend_name=backend_name,
        local_health=local_health,
        s3_health=s3_health,
        artifact_summary=artifact_summary,
        retention_policy=retention_policy,
        backend_status=backend_status,
    )
    readiness_monitor = {
        'enabled': bool(current_app.config.get('REPORT_STORAGE_HEALTH_MONITOR_ENABLED', True)),
        'interval_minutes': int(current_app.config.get('REPORT_STORAGE_HEALTH_INTERVAL_MINUTES', 1) or 1),
        'stale_seconds': int(current_app.config.get('REPORT_STORAGE_HEALTH_STALE_SECONDS', 120) or 120),
        'checked_label': format_storage_check_age(backend_status),
        'source': str(backend_status.get('source') or 'direct'),
        'source_label': format_storage_check_source(backend_status),
        'shared_state': bool(current_app.config.get('REDIS_URL')),
    }
    storage_posture = build_storage_operations_posture(
        backend_name=backend_name,
        backend_status=backend_status,
        artifact_summary=artifact_summary,
        readiness_monitor=readiness_monitor,
    )

    return {
        'page_title': 'Reports Storage',
        'page_subtitle': 'Review report artifact storage, integrity, retention readiness, and backend health before generation or retrieval operations.',
        'active_backend': backend_name,
        'workspace': normalize_storage_workspace(workspace),
        'backend_status': backend_status,
        'storage_actions_enabled': bool(backend_status.get('reachable', False)),
        'readiness_monitor': readiness_monitor,
        'storage_posture': storage_posture,
        'summary_cards': summary_cards,
        'supported_backends': [
            {
                'value': 'local',
                'label': 'Local filesystem',
                'description': 'Store generated report PDF and Excel artifacts in the application filesystem.',
                'is_active': backend_name == 'local',
                'tone': 'green' if backend_name == 'local' else 'slate',
            },
            {
                'value': 's3',
                'label': 'S3-compatible storage',
                'description': 'Store generated report PDF and Excel artifacts in AWS S3, MinIO, or another S3-compatible backend.',
                'is_active': backend_name == 's3',
                'tone': 'green' if backend_name == 's3' else 'slate',
            },
        ],
        'local': local_health,
        's3': s3_health,
        'artifact_summary': artifact_summary,
        'retention_policy': retention_policy,
        'lifecycle_summary': lifecycle_summary,
        'configuration_source': 'Environment / config.py',
        'is_mutable_from_ui': False,
        'object_key_format': (
            'reports/YYYY/MM/<cluster_slug>/<report_type_slug>/'
            'report-<id>-<type>-<cluster>-<namespace>-<period>-<timestamp>-<uuid>.<ext>'
        ),
        'verification': {
            'mode': 'Manual verification',
            'description': 'Use Test Storage to write, check, and delete a small verification object using the active backend.',  # noqa: E501
            'action_query': 'verify=1',
        },
        'integrity_check': {
            'mode': 'Manual integrity scan',
            'description': (
                'Validate stored report references against the active backend. Read-only; nothing is deleted.'
            ),
            'action_query': 'integrity=1',
            'max_items': 500,
        },
        'integrity_result': None,
        'cleanup_dry_run': {
            'mode': 'Read-only cleanup preview',
            'description': ('Preview records that match retention rules without deleting artifacts or database rows.'),
            'action_query': 'cleanup_dry_run=1',
            'default_retention_days': get_cleanup_dry_run_retention_days(),
            'max_items': 500,
        },
        'cleanup_dry_run_result': None,
        'notes': [
            'Storage configuration is read from environment variables and application configuration.',
            'Secrets should be provided through environment variables or Kubernetes Secrets.',
            'The UI is read-only for configuration; it only displays status and can run a verification check.',
            'Existing report records keep their backend prefix, so local and S3 artifacts can coexist.',
            'Retention cleanup remains a read-only preview unless destructive cleanup is explicitly enabled and governed.',  # noqa: E501
        ],
        'recommended_actions': build_storage_recommended_actions(
            backend_name,
            local_health,
            s3_health,
        ),
    }


def build_storage_lifecycle_summary(
    *,
    backend_name: str,
    local_health: dict[str, Any],
    s3_health: dict[str, Any],
    artifact_summary: dict[str, Any],
    retention_policy: dict[str, Any],
    backend_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_backend_status = dict(backend_status or {})
    backend_ready = bool(resolved_backend_status.get('available', False))
    backend_label = str(resolved_backend_status.get('title') or 'Storage backend needs review')
    backend_description = str(
        resolved_backend_status.get('description') or 'The active storage backend is configured but needs verification.'
    )

    if not resolved_backend_status:
        if backend_name == 'local':
            backend_ready = bool(local_health.get('root_writable', False))
        elif backend_name == 's3':
            backend_ready = bool(s3_health.get('configuration_complete', False))

    reports_with_files = int(
        artifact_summary.get(
            'reports_with_files',
            0,
        )
        or 0
    )
    ready_reports = int(
        artifact_summary.get(
            'ready_reports',
            0,
        )
        or 0
    )

    if not backend_ready:
        level = 'warning'
        label = backend_label
        description = backend_description
        icon = 'circle-alert'
        class_name = 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300'
    else:
        level = 'healthy'
        label = 'Storage lifecycle healthy'
        description = 'Generated report storage is active and current artifact records use backend-aware storage URIs.'
        icon = 'shield-check'
        class_name = 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300'

    checks = [
        {
            'label': 'Active backend',
            'value': backend_name.upper(),
            'status': 'pass' if backend_ready else 'warning',
            'description': backend_description,
        },
        {
            'label': 'Stored artifacts',
            'value': str(
                reports_with_files,
            ),
            'status': 'pass' if reports_with_files > 0 else 'info',
            'description': 'Generated report records with a canonical storage URI.',
        },
        {
            'label': 'Ready reports',
            'value': str(
                ready_reports,
            ),
            'status': 'pass' if ready_reports > 0 else 'info',
            'description': 'Reports marked ready in the database.',
        },
        {
            'label': 'Cleanup mode',
            'value': str(
                retention_policy.get(
                    'mode',
                    'Disabled',
                )
            ),
            'status': 'info',
            'description': 'Retention is defined; destructive cleanup remains guarded by configuration and approval workflow.',  # noqa: E501
        },
    ]

    return {
        'level': level,
        'label': label,
        'description': description,
        'icon': icon,
        'class': class_name,
        'backend_ready': backend_ready,
        'checks': checks,
    }


def build_storage_recommended_actions(
    backend_name: str,
    local_health: dict[str, Any],
    s3_health: dict[str, Any],
) -> list[dict[str, str]]:
    actions = [
        {
            'label': 'Generate a fresh report',
            'description': 'Create a new report and confirm the file_path uses the active backend prefix.',
            'href': '/reports/generate',
        },
        {
            'label': 'Run storage verification',
            'description': 'Use Test Storage after changing ENV values or switching backend.',
            'href': '#storage-verification',
        },
        {
            'label': 'Check artifact integrity',
            'description': 'Run a read-only scan to confirm DB storage URIs still point to existing artifacts.',
            'href': '#artifact-integrity',
        },
    ]

    if backend_name == 'local' and not local_health.get(
        'root_writable',
        False,
    ):
        actions.append(
            {
                'label': 'Fix local path permission',
                'description': 'The local storage root is not writable by the running application user.',
                'href': '#local-storage',
            }
        )

    if backend_name == 's3' and not s3_health.get(
        'configuration_complete',
        False,
    ):
        actions.append(
            {
                'label': 'Complete S3 configuration',
                'description': 'Confirm bucket, boto3 dependency, credentials, endpoint, and path-style setting.',
                'href': '#s3-storage',
            }
        )

    actions.append(
        {
            'label': 'Run cleanup dry run',
            'description': 'Preview retention candidates without deleting local or S3 artifacts.',
            'href': '#cleanup-dry-run',
        }
    )

    actions.append(
        {
            'label': 'Review retention policy',
            'description': 'Review defined retention age, cleanup scope, orphan detection, and audit requirements before enabling destructive deletes.',  # noqa: E501
            'href': '#retention-policy',
        }
    )

    actions.append(
        {
            'label': 'Review generated artifacts',
            'description': 'Open Generated Reports to validate download state and artifact metadata.',
            'href': '/reports/generated',
        }
    )

    return actions


def verify_active_report_storage() -> dict[str, Any]:
    backend = get_active_report_storage_backend()
    backend_name = get_configured_storage_backend_name()
    test_key = 'reports/storage-verification/kaori-report-storage-check.txt'

    with NamedTemporaryFile(
        mode='w',
        encoding='utf-8',
        suffix='.txt',
        delete=False,
    ) as temp_file:
        temp_file.write('kaori report storage verification\n')
        temp_path = Path(temp_file.name)

    try:
        if backend_name == 's3' and hasattr(backend, 'test_connection'):
            backend.test_connection()  # type: ignore[attr-defined]

        stored_file = backend.save_file(
            source_path=temp_path,
            object_key=test_key,
        )
        exists = backend.exists(stored_file.object_key)
        backend.delete(stored_file.object_key)
        readiness = (
            refresh_report_storage_readiness(
                backend_name,
                source='manual_verification',
            )
            if exists
            else mark_report_storage_backend_unavailable(
                backend_name,
                source='manual_verification_failure',
            )
        )
        return {
            'backend': backend_name,
            'uri': stored_file.uri,
            'object_key': stored_file.object_key,
            'size_bytes': stored_file.size_bytes,
            'exists_after_upload': exists,
            'verified': exists,
            'readiness': readiness,
        }
    except Exception:
        mark_report_storage_backend_unavailable(
            backend_name,
            source='manual_verification_failure',
        )
        raise
    finally:
        temp_path.unlink(missing_ok=True)


def scan_report_storage_integrity(
    max_items: int = 500,
) -> dict[str, Any]:
    checked_reports = (
        db.session.execute(
            select(
                Report,
            )
            .where(
                Report.file_path.is_not(
                    None,
                ),
                Report.file_path != '',
            )
            .order_by(
                Report.updated_at.desc(),
                Report.id.desc(),
            )
            .limit(
                max_items,
            )
        )
        .scalars()
        .all()
    )

    available_count = 0
    missing_count = 0
    error_count = 0
    backend_counts: dict[str, int] = {
        'local': 0,
        's3': 0,
        'unknown': 0,
    }
    missing_samples: list[dict[str, str]] = []
    error_samples: list[dict[str, str]] = []

    for report in checked_reports:
        stored_path = report.file_path or ''

        try:
            backend_name, _object_key = parse_report_storage_uri(
                stored_path,
            )
        except Exception:
            backend_name = 'unknown'

        backend_counts[backend_name] = (
            backend_counts.get(
                backend_name,
                0,
            )
            + 1
        )

        try:
            exists = report_file_exists(
                stored_path,
            )
        except Exception:
            error_count += 1

            if (
                len(
                    error_samples,
                )
                < 10
            ):
                error_samples.append(
                    {
                        'report_id': str(
                            report.id,
                        ),
                        'name': report.name,
                        'file_path': stored_path,
                        'backend': backend_name,
                        'error': 'Storage backend was unavailable during this integrity check.',
                    }
                )

            continue

        if exists:
            available_count += 1
            continue

        missing_count += 1

        if (
            len(
                missing_samples,
            )
            < 10
        ):
            missing_samples.append(
                {
                    'report_id': str(
                        report.id,
                    ),
                    'name': report.name,
                    'file_path': stored_path,
                    'backend': backend_name,
                }
            )

    checked_count = len(
        checked_reports,
    )

    return {
        'checked_count': checked_count,
        'available_count': available_count,
        'missing_count': missing_count,
        'error_count': error_count,
        'backend_counts': backend_counts,
        'missing_samples': missing_samples,
        'error_samples': error_samples,
        'max_items': max_items,
        'is_limited': checked_count >= max_items,
        'is_healthy': missing_count == 0 and error_count == 0,
    }


def get_cleanup_dry_run_retention_days() -> int:
    configured_days = current_app.config.get(
        'REPORT_RETENTION_DAYS',
        90,
    )

    try:
        retention_days = int(
            configured_days,
        )
    except (TypeError, ValueError):
        retention_days = 90

    return max(
        retention_days,
        1,
    )


def build_report_cleanup_dry_run(
    retention_days: int | None = None,
    max_items: int = 500,
) -> dict[str, Any]:
    effective_retention_days = retention_days or get_cleanup_dry_run_retention_days()
    cutoff_at = datetime.now(
        UTC,
    ) - timedelta(
        days=effective_retention_days,
    )

    candidate_reports = (
        db.session.execute(
            select(
                Report,
            )
            .where(
                Report.file_path.is_not(
                    None,
                ),
                Report.file_path != '',
                Report.status.in_(
                    ['ready', 'archived'],
                ),
                Report.updated_at <= cutoff_at,
            )
            .order_by(
                Report.updated_at.asc(),
                Report.id.asc(),
            )
            .limit(
                max_items,
            )
        )
        .scalars()
        .all()
    )

    total_candidates = 0
    available_candidates = 0
    missing_reference_candidates = 0
    error_candidates = 0
    candidate_size_bytes = 0
    status_counts: dict[str, int] = {}
    backend_counts: dict[str, int] = {
        'local': 0,
        's3': 0,
        'unknown': 0,
    }
    sample_candidates: list[dict[str, str]] = []
    missing_samples: list[dict[str, str]] = []
    error_samples: list[dict[str, str]] = []

    for report in candidate_reports:
        stored_path = report.file_path or ''
        total_candidates += 1
        status_counts[report.status] = (
            status_counts.get(
                report.status,
                0,
            )
            + 1
        )
        candidate_size_bytes += report.file_size_bytes or 0

        try:
            backend_name, _object_key = parse_report_storage_uri(
                stored_path,
            )
        except Exception:
            backend_name = 'unknown'

        backend_counts[backend_name] = (
            backend_counts.get(
                backend_name,
                0,
            )
            + 1
        )

        try:
            exists = report_file_exists(
                stored_path,
            )
        except Exception:
            error_candidates += 1

            if (
                len(
                    error_samples,
                )
                < 10
            ):
                error_samples.append(
                    build_cleanup_sample(
                        report,
                        stored_path,
                        backend_name,
                        error='Storage backend was unavailable during this cleanup preview.',
                    )
                )

            continue

        if exists:
            available_candidates += 1

            if (
                len(
                    sample_candidates,
                )
                < 10
            ):
                sample_candidates.append(
                    build_cleanup_sample(
                        report,
                        stored_path,
                        backend_name,
                    )
                )

            continue

        missing_reference_candidates += 1

        if (
            len(
                missing_samples,
            )
            < 10
        ):
            missing_samples.append(
                build_cleanup_sample(
                    report,
                    stored_path,
                    backend_name,
                )
            )

    return {
        'mode': 'dry_run',
        'cleanup_enabled': False,
        'cleanup_scope': 'ready-and-archived-artifacts',
        'retention_days': effective_retention_days,
        'cutoff_at': cutoff_at.strftime(
            '%d %b %Y %H:%M UTC',
        ),
        'max_items': max_items,
        'is_limited': len(
            candidate_reports,
        )
        >= max_items,
        'candidate_count': total_candidates,
        'available_candidate_count': available_candidates,
        'missing_reference_count': missing_reference_candidates,
        'error_count': error_candidates,
        'candidate_size': format_cleanup_file_size(
            candidate_size_bytes,
        ),
        'candidate_size_bytes': candidate_size_bytes,
        'status_counts': status_counts,
        'backend_counts': backend_counts,
        'sample_candidates': sample_candidates,
        'missing_samples': missing_samples,
        'error_samples': error_samples,
        'is_empty': total_candidates == 0,
    }


def build_cleanup_sample(
    report: Report,
    stored_path: str,
    backend_name: str,
    error: str | None = None,
) -> dict[str, str]:
    item = {
        'report_id': str(
            report.id,
        ),
        'name': report.name,
        'status': report.status,
        'backend': backend_name,
        'file_path': stored_path,
        'updated_at': report.updated_at.strftime(
            '%d %b %Y %H:%M UTC',
        )
        if report.updated_at
        else '-',
        'file_size': format_cleanup_file_size(
            report.file_size_bytes or 0,
        ),
    }

    if error:
        item['error'] = error

    return item


def format_cleanup_file_size(
    value: int | None,
) -> str:
    if value is None:
        return 'Not available'

    if value < 1024:
        return f'{value} B'

    if value < 1024 * 1024:
        return f'{value / 1024:.2f} KB'

    if value < 1024 * 1024 * 1024:
        return f'{value / (1024 * 1024):.2f} MB'

    return f'{value / (1024 * 1024 * 1024):.2f} GB'
