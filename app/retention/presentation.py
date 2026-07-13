from __future__ import annotations

from typing import Any

from flask import current_app

from app.models.archive import ArchiveArtifact
from app.retention.domains import get_archive_domain
from app.retention.service import paginate_archives, preview_retention
from app.storage.service import build_storage_profile


def build_activity_retention_context(
    *,
    include_preview: bool = False,
    archive_page: int = 1,
    archive_per_page: int = 5,
) -> dict[str, Any]:
    domain = get_archive_domain('operational_activity')
    policy = domain.build_policy()
    storage_profile = build_storage_profile('archive')
    archive_pagination = paginate_archives(
        domain_name=domain.name,
        page=archive_page,
        per_page=archive_per_page,
    )
    preview = preview_retention(domain.name) if include_preview else None

    return {
        'domain': domain.name,
        'enabled': policy.enabled,
        'retention_days': policy.retention_days,
        'archive_retention_days': policy.archive_retention_days,
        'batch_size': policy.batch_size,
        'protect_unreviewed': policy.protect_unreviewed,
        'protected_max_days': policy.protected_max_days,
        'schedule_enabled': _bool_config('ACTIVITY_RETENTION_SCHEDULE_ENABLED', True),
        'schedule_hour': _int_config('ACTIVITY_RETENTION_SCHEDULE_HOUR', 2),
        'schedule_minute': _int_config('ACTIVITY_RETENTION_SCHEDULE_MINUTE', 15),
        'schedule_timezone': str(current_app.config.get('CELERY_TIMEZONE', 'UTC') or 'UTC'),
        'storage_backend': storage_profile.backend,
        'storage_location': _storage_location(storage_profile),
        'archive_format': 'JSONL.GZ + manifest JSON',
        'preview': _serialize_preview(preview) if preview is not None else None,
        'archives': [_serialize_archive(item) for item in archive_pagination.items],
        'archive_pagination': {
            'page': archive_pagination.page,
            'pages': archive_pagination.pages,
            'per_page': archive_pagination.per_page,
            'total': archive_pagination.total,
            'has_prev': archive_pagination.has_prev,
            'has_next': archive_pagination.has_next,
            'prev_num': archive_pagination.prev_num,
            'next_num': archive_pagination.next_num,
        },
    }


def _serialize_preview(preview: dict[str, Any]) -> dict[str, Any]:
    boundary = preview['boundary']
    return {
        'record_count': boundary.record_count,
        'cutoff_at': boundary.cutoff_at,
        'range_start': boundary.range_start,
        'range_end': boundary.range_end,
        'maximum_record_id': boundary.maximum_record_id,
        'protected_record_count': boundary.protected_record_count,
        'estimated_uncompressed_bytes': preview['estimated_uncompressed_bytes'],
    }


def _serialize_archive(artifact: ArchiveArtifact) -> dict[str, Any]:
    return {
        'id': artifact.id,
        'status': artifact.status,
        'trigger_type': artifact.trigger_type,
        'operation_mode': artifact.operation_mode,
        'record_count': artifact.record_count,
        'cleanup_deleted_count': artifact.cleanup_deleted_count,
        'storage_backend': artifact.storage_backend,
        'size_bytes': artifact.size_bytes,
        'size_label': _format_size(artifact.size_bytes),
        'checksum_sha256': artifact.checksum_sha256,
        'range_start': artifact.range_start,
        'range_end': artifact.range_end,
        'created_at': artifact.created_at,
        'completed_at': artifact.completed_at,
        'error_message': artifact.error_message,
        'is_downloadable': artifact.is_downloadable,
        'is_verifiable': artifact.is_verifiable,
    }


def _storage_location(profile) -> str:
    if profile.backend == 'local':
        return str(profile.local_root)
    prefix = f'/{profile.s3_prefix}' if profile.s3_prefix else ''
    return f's3://{profile.s3_bucket}{prefix}'


def _bool_config(key: str, default: bool) -> bool:
    value = current_app.config.get(key, default)
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def _int_config(key: str, default: int) -> int:
    try:
        return int(current_app.config.get(key, default))
    except (TypeError, ValueError):
        return default


def _format_size(value: int | None) -> str:
    size = float(value or 0)
    units = ('B', 'KB', 'MB', 'GB', 'TB')
    unit = units[0]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            break
        size /= 1024
    return f'{size:.1f} {unit}' if unit != 'B' else f'{int(size)} B'
