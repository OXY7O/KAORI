from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any

from flask import current_app
from sqlalchemy import func, select

from app.extensions.db import db
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


def build_storage_retention_policy() -> dict[str, Any]:
    """Return the current retention and cleanup policy status.

    KAORI defines the retention contract while keeping delete operations
    guarded. The policy is visible in the UI and cleanup dry-run uses the same
    retention age, but destructive deletion still requires an explicit
    admin workflow.
    """
    retention_days = _safe_int_config(
        'REPORT_RETENTION_DAYS',
        90,
    )
    archive_retention_days = _safe_int_config(
        'REPORT_ARCHIVE_RETENTION_DAYS',
        180,
    )
    cleanup_mode = (
        str(
            current_app.config.get(
                'REPORT_CLEANUP_MODE',
                'dry-run-only',
            )
            or 'dry-run-only'
        )
        .strip()
        .lower()
    )
    cleanup_scope = str(
        current_app.config.get(
            'REPORT_CLEANUP_SCOPE',
            'ready-and-archived-artifacts',
        )
        or 'ready-and-archived-artifacts'
    ).strip()
    orphan_detection_enabled = parse_bool_config(
        current_app.config.get(
            'REPORT_ORPHAN_DETECTION_ENABLED',
            True,
        )
    )
    destructive_actions_enabled = parse_bool_config(
        current_app.config.get(
            'REPORT_DESTRUCTIVE_CLEANUP_ENABLED',
            False,
        )
    )
    auto_cleanup_enabled = cleanup_mode == 'automatic' and destructive_actions_enabled
    manual_cleanup_enabled = cleanup_mode in {'manual', 'automatic'} and destructive_actions_enabled

    return {
        'status': 'Defined',
        'mode': 'Dry-run only' if not destructive_actions_enabled else cleanup_mode.replace('-', ' ').title(),
        'auto_cleanup_enabled': auto_cleanup_enabled,
        'manual_cleanup_enabled': manual_cleanup_enabled,
        'orphan_detection_enabled': orphan_detection_enabled,
        'orphan_cleanup_enabled': destructive_actions_enabled and orphan_detection_enabled,
        'destructive_actions_enabled': destructive_actions_enabled,
        'retention_days': f'{retention_days} days',
        'retention_days_value': retention_days,
        'archive_retention_days': f'{archive_retention_days} days',
        'archive_retention_days_value': archive_retention_days,
        'cleanup_scope': cleanup_scope,
        'audit_status': 'Required before destructive cleanup'
        if not destructive_actions_enabled
        else 'Required for every cleanup run',
        'safe_regenerate_behavior': (
            'Regeneration creates a new artifact. Previous artifacts remain available until they exceed the defined retention window and an approved cleanup workflow is enabled.'  # noqa: E501
        ),
        'description': (
            'Retention is enforced as a read-only cleanup preview. Destructive local or S3 deletion remains guarded until approval, audit logging, and confirmation controls are enabled.'  # noqa: E501
        ),
        'policy_rules': [
            f'Ready/generated artifacts are retention candidates after {retention_days} days.',
            f'Archived artifacts are long-term evidence and are reviewed after {archive_retention_days} days.',
            'Missing database references are reported by integrity scan before any cleanup decision.',
            'S3-compatible and local artifacts use the same retention rule, but storage backend prefixes are preserved.',  # noqa: E501
            'No file or object is deleted unless REPORT_DESTRUCTIVE_CLEANUP_ENABLED is explicitly enabled in configuration.',  # noqa: E501
        ],
        'next_steps': [
            'Use Cleanup Dry Run to review candidate reports before enabling any delete action.',
            'Confirm audit logging and admin-only approval before turning on destructive cleanup.',
            'Keep archived reports longer than normal ready reports because they may be used as operational evidence.',
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
