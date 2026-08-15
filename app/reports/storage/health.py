from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any

from flask import current_app
from sqlalchemy import func, select

from app.extensions.db import db
from app.models.lifecycle import DataLifecyclePolicy
from app.models.report import Report


def parse_bool_config(
    value: object,
) -> bool:
    if isinstance(
        value,
        bool,
    ):
        return value

    return str(
        value or '',
    ).strip().lower() in {
        '1',
        'true',
        'yes',
        'on',
    }


def resolve_app_path(
    configured_path: str | Path | None,
    default_path: Path,
) -> Path:
    if configured_path:
        resolved_path = Path(
            configured_path,
        )
    else:
        resolved_path = default_path

    if not resolved_path.is_absolute():
        resolved_path = (
            Path(
                current_app.root_path,
            ).parent
            / resolved_path
        )

    return resolved_path.resolve()


def get_local_storage_root_path() -> Path:
    configured_root = current_app.config.get(
        'REPORT_LOCAL_STORAGE_DIR',
    )

    return resolve_app_path(
        configured_root,
        Path(
            current_app.instance_path,
        ),
    )


def get_render_staging_path() -> Path:
    return resolve_app_path(
        current_app.config.get(
            'REPORT_RENDER_STAGING_DIR',
            'instance/report-render-staging',
        ),
        Path(
            current_app.instance_path,
        )
        / 'report-render-staging',
    )


def get_download_cache_path() -> Path:
    return resolve_app_path(
        current_app.config.get(
            'REPORT_DOWNLOAD_CACHE_DIR',
            'instance/report-download-cache',
        ),
        Path(
            current_app.instance_path,
        )
        / 'report-download-cache',
    )


def build_local_storage_health() -> dict[str, Any]:
    root_path = get_local_storage_root_path()
    reports_path = root_path / 'reports'
    staging_path = get_render_staging_path()
    cache_path = get_download_cache_path()

    return {
        'root_path': str(
            root_path,
        ),
        'reports_path': str(
            reports_path,
        ),
        'render_staging_path': str(
            staging_path,
        ),
        'download_cache_path': str(
            cache_path,
        ),
        'root_exists': root_path.exists(),
        'reports_path_exists': reports_path.exists(),
        'root_writable': is_path_writable(
            root_path,
        ),
        'reports_file_count': count_files_safe(
            reports_path,
        ),
        'reports_total_size': format_file_size(
            sum_files_size_safe(
                reports_path,
            )
        ),
    }


def build_s3_storage_health() -> dict[str, Any]:
    bucket = str(
        current_app.config.get(
            'REPORT_S3_BUCKET',
            '',
        )
        or ''
    ).strip()
    region = str(
        current_app.config.get(
            'REPORT_S3_REGION',
            'us-east-1',
        )
        or 'us-east-1'
    ).strip()
    endpoint_url = str(
        current_app.config.get(
            'REPORT_S3_ENDPOINT_URL',
            '',
        )
        or ''
    ).strip()
    prefix = (
        str(
            current_app.config.get(
                'REPORT_S3_PREFIX',
                '',
            )
            or ''
        )
        .strip()
        .strip('/')
    )
    access_key = str(
        current_app.config.get(
            'REPORT_S3_ACCESS_KEY_ID',
            '',
        )
        or ''
    ).strip()
    secret_key = str(
        current_app.config.get(
            'REPORT_S3_SECRET_ACCESS_KEY',
            '',
        )
        or ''
    ).strip()
    force_path_style = parse_bool_config(
        current_app.config.get(
            'REPORT_S3_FORCE_PATH_STYLE',
            False,
        )
    )

    boto3_available = (
        importlib.util.find_spec(
            'boto3',
        )
        is not None
    )

    explicit_credentials_configured = bool(
        access_key and secret_key,
    )

    return {
        'bucket': bucket or 'Not configured',
        'bucket_configured': bool(
            bucket,
        ),
        'region': region,
        'endpoint_url': endpoint_url or 'AWS default endpoint',
        'endpoint_mode': 'Custom endpoint / MinIO-compatible' if endpoint_url else 'AWS managed endpoint',
        'prefix': prefix or 'No prefix',
        'force_path_style': force_path_style,
        'boto3_available': boto3_available,
        'access_key_configured': bool(
            access_key,
        ),
        'secret_key_configured': bool(
            secret_key,
        ),
        'credential_mode': 'Explicit access key from ENV'
        if explicit_credentials_configured
        else 'IAM role / ambient AWS credentials',
        'configuration_complete': bool(
            bucket and boto3_available,
        ),
        'bucket_reachability': 'Use Test Storage to verify bucket access.',
    }


def get_generated_report_hot_retention_days() -> int:
    stored = DataLifecyclePolicy.query.filter_by(domain='generated_report').first()
    configured_days = (
        stored.hot_retention_days
        if stored is not None
        else current_app.config.get(
            'GENERATED_REPORT_RETENTION_DAYS',
            current_app.config.get('REPORT_RETENTION_DAYS', 90),
        )
    )
    try:
        return max(int(configured_days), 1)
    except (TypeError, ValueError):
        return 90


def build_storage_retention_policy() -> dict[str, Any]:
    """Describe the Generated Reports lifecycle policy owned by Data Lifecycle."""
    stored = DataLifecyclePolicy.query.filter_by(domain='generated_report').first()
    retention_days = (
        max(int(stored.hot_retention_days), 1)
        if stored is not None
        else _safe_int_config(
            'GENERATED_REPORT_RETENTION_DAYS',
            _safe_int_config('REPORT_RETENTION_DAYS', 90),
        )
    )
    archive_retention_days = (
        max(int(stored.archive_retention_days), 1)
        if stored is not None
        else _safe_int_config(
            'GENERATED_REPORT_ARCHIVE_RETENTION_DAYS',
            _safe_int_config('REPORT_ARCHIVE_RETENTION_DAYS', 365),
        )
    )
    settings = dict(stored.settings_json or {}) if stored is not None else {}
    failed_retention_days = max(int(settings.get('failed_retention_days') or 30), 1)
    archived_retention_days = max(
        int(settings.get('archived_retention_days') or max(retention_days, 180)),
        retention_days,
    )
    lifecycle_enabled = (
        bool(stored.enabled)
        if stored is not None
        else parse_bool_config(current_app.config.get('GENERATED_REPORT_RETENTION_ENABLED', False))
    )
    schedule_enabled = bool(stored.schedule_enabled) if stored is not None else False

    return {
        'status': 'Lifecycle Managed' if lifecycle_enabled else 'Lifecycle Paused',
        'mode': (
            str(stored.operation_mode).replace('_', ' ').title() if stored is not None else 'Archive Then Cleanup'
        ),
        'auto_cleanup_enabled': lifecycle_enabled and schedule_enabled,
        'manual_cleanup_enabled': lifecycle_enabled,
        'orphan_detection_enabled': parse_bool_config(current_app.config.get('REPORT_ORPHAN_DETECTION_ENABLED', True)),
        'orphan_cleanup_enabled': False,
        'destructive_actions_enabled': lifecycle_enabled,
        'retention_days': retention_days,
        'archive_retention_days': archive_retention_days,
        'cleanup_scope': 'Generated Reports lifecycle domain',
        'audit_status': 'Archive verification required before cleanup',
        'safe_regenerate_behavior': (
            'Regeneration refreshes the report hot-retention age. Active generation is protected from lifecycle cleanup.'
        ),
        'description': (
            'Platform Operations → Data Lifecycle is the canonical owner for Generated Reports retention. '
            'Ready and Archived binary artifacts are copied and checksum-verified before source cleanup.'
        ),
        'policy_rules': [
            f'Ready reports remain in the hot registry for {retention_days} days.',
            f'Failed report metadata remains hot for {failed_retention_days} days.',
            f'Manually Archived reports remain hot for {archived_retention_days} days.',
            f'Verified lifecycle archives are retained for {archive_retention_days} days.',
            'Requested, Queued, Generating, and active regeneration jobs are excluded from cleanup.',
        ],
        'next_steps': [
            'Open Platform Operations → Data Lifecycle to preview or edit the Generated Reports policy.',
            'Use Reports Storage integrity checks to investigate missing or unreachable source artifacts.',
            'Keep archive storage independently backed up when Generated Reports are operational evidence.',
        ],
    }


def _safe_int_config(
    key: str,
    default: int,
) -> int:
    try:
        value = int(
            current_app.config.get(
                key,
                default,
            )
        )
    except (TypeError, ValueError):
        return default

    return max(
        value,
        1,
    )


def build_storage_artifact_summary() -> dict[str, Any]:
    total_reports = count_reports()
    ready_reports = count_reports_by_status(
        'ready',
    )
    local_reports = count_reports_by_file_prefix(
        'local:',
    )
    s3_reports = count_reports_by_file_prefix(
        's3:',
    )
    reports_with_files = count_reports_with_file_path()
    total_size_bytes = sum_report_file_size_bytes()
    retention_policy = build_storage_retention_policy()

    return {
        'total_reports': total_reports,
        'ready_reports': ready_reports,
        'reports_with_files': reports_with_files,
        'local_reports': local_reports,
        's3_reports': s3_reports,
        'total_size': format_file_size(
            total_size_bytes,
        ),
        'total_size_bytes': total_size_bytes,
        'retention_policy': retention_policy,
        'cleanup_mode': retention_policy['mode'],
        'auto_cleanup_enabled': retention_policy['auto_cleanup_enabled'],
        'orphan_detection_enabled': retention_policy['orphan_detection_enabled'],
    }


def build_storage_summary_cards(
    active_backend: str,
) -> list[dict[str, str]]:
    artifact_summary = build_storage_artifact_summary()
    local_health = build_local_storage_health()
    s3_health = build_s3_storage_health()

    s3_status = 'Configured' if s3_health['configuration_complete'] else 'Incomplete'
    s3_caption = (
        'Bucket and boto3 are ready' if s3_health['configuration_complete'] else 'Complete S3 config before use'
    )

    return [
        {
            'label': 'Active Backend',
            'value': active_backend.upper(),
            'caption': 'Resolved from ENV / config.py',
            'icon': 'hard-drive',
            'tone': 'green' if active_backend in {'local', 's3'} else 'amber',
        },
        {
            'label': 'Stored Reports',
            'value': str(
                artifact_summary['reports_with_files'],
            ),
            'caption': f'{artifact_summary["total_size"]} tracked in database',
            'icon': 'files',
            'tone': 'blue',
        },
        {
            'label': 'Local Path',
            'value': 'Writable' if local_health['root_writable'] else 'Check path',
            'caption': 'Local filesystem backend status',
            'icon': 'folder-check',
            'tone': 'green' if local_health['root_writable'] else 'red',
        },
        {
            'label': 'S3 Compatible',
            'value': s3_status,
            'caption': s3_caption,
            'icon': 'cloud',
            'tone': 'green' if s3_health['configuration_complete'] else 'amber',
        },
    ]


def count_reports() -> int:
    return (
        db.session.scalar(
            select(
                func.count(
                    Report.id,
                )
            )
        )
        or 0
    )


def count_reports_by_status(
    status: str,
) -> int:
    return (
        db.session.scalar(
            select(
                func.count(
                    Report.id,
                )
            ).where(
                Report.status == status,
            )
        )
        or 0
    )


def count_reports_with_file_path() -> int:
    return (
        db.session.scalar(
            select(
                func.count(
                    Report.id,
                )
            ).where(
                Report.file_path.is_not(
                    None,
                ),
                Report.file_path != '',
            )
        )
        or 0
    )


def count_reports_by_file_prefix(
    prefix: str,
) -> int:
    return (
        db.session.scalar(
            select(
                func.count(
                    Report.id,
                )
            ).where(
                Report.file_path.ilike(
                    f'{prefix}%',
                )
            )
        )
        or 0
    )


def sum_report_file_size_bytes() -> int:
    return (
        db.session.scalar(
            select(
                func.coalesce(
                    func.sum(
                        Report.file_size_bytes,
                    ),
                    0,
                )
            )
        )
        or 0
    )


def count_files_safe(
    directory: Path,
) -> int:
    if not directory.exists() or not directory.is_dir():
        return 0

    return sum(
        1
        for path in directory.rglob(
            '*',
        )
        if path.is_file()
    )


def sum_files_size_safe(
    directory: Path,
) -> int:
    if not directory.exists() or not directory.is_dir():
        return 0

    total_size = 0

    for path in directory.rglob(
        '*',
    ):
        if path.is_file():
            try:
                total_size += path.stat().st_size
            except OSError:
                continue

    return total_size


def is_path_writable(
    path: Path,
) -> bool:
    target = path

    while not target.exists() and target.parent != target:
        target = target.parent

    if not target.exists():
        return False

    return os.access(
        target,
        os.W_OK,
    )


def format_file_size(
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
