from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from flask import current_app
from sqlalchemy import select

from app.extensions import db
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
from app.storage.base import ArtifactStorageBackend, StoredArtifact

SUPPORTED_REPORT_STORAGE_BACKENDS = {
    'local',
    's3',
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
) -> StoredArtifact:
    backend = get_active_report_storage_backend()

    return backend.save_file(
        source_path=source_path,
        object_key=object_key,
    )


def build_report_download_path(
    stored_path: str,
) -> Path:
    backend_name, object_key = parse_report_storage_uri(
        stored_path,
    )

    backend = build_report_storage_backend(
        backend_name,
    )

    return backend.build_download_path(
        object_key,
    )


def report_file_exists(
    stored_path: str,
) -> bool:
    backend_name, object_key = parse_report_storage_uri(
        stored_path,
    )

    backend = build_report_storage_backend(
        backend_name,
    )

    return backend.exists(
        object_key,
    )


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


def get_report_storage_payload() -> dict[str, Any]:
    backend_name = get_configured_storage_backend_name()
    local_health = build_local_storage_health()
    s3_health = build_s3_storage_health()
    artifact_summary = build_storage_artifact_summary()
    retention_policy = build_storage_retention_policy()
    lifecycle_summary = build_storage_lifecycle_summary(
        backend_name=backend_name,
        local_health=local_health,
        s3_health=s3_health,
        artifact_summary=artifact_summary,
        retention_policy=retention_policy,
    )

    return {
        'page_title': 'Reports Storage',
        'page_subtitle': 'Monitor generated report artifact storage, backend configuration, and verification status.',
        'active_backend': backend_name,
        'summary_cards': build_storage_summary_cards(
            backend_name,
        ),
        'supported_backends': [
            {
                'value': 'local',
                'label': 'Local filesystem',
                'description': 'Store generated report PDFs in the application filesystem.',
                'is_active': backend_name == 'local',
                'tone': 'green' if backend_name == 'local' else 'slate',
            },
            {
                'value': 's3',
                'label': 'S3-compatible storage',
                'description': 'Store generated report PDFs in AWS S3, MinIO, or another S3-compatible backend.',
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
            'report-<id>-<type>-<cluster>-<namespace>-<period>-<timestamp>-<uuid>.pdf'
        ),
        'verification': {
            'mode': 'Manual verification',
            'description': 'Use Test Storage to write, check, and delete a small verification object using the active backend.',  # noqa: E501
            'action_query': 'verify=1',
        },
        'integrity_check': {
            'mode': 'Manual integrity scan',
            'description': (
                'Use Check Artifact Integrity to validate database file_path references against the configured storage backends. '  # noqa: E501
                'This is read-only and does not delete local or S3 objects.'
            ),
            'action_query': 'integrity=1',
            'max_items': 500,
        },
        'integrity_result': None,
        'cleanup_dry_run': {
            'mode': 'Read-only cleanup preview',
            'description': (
                'Use Cleanup Dry Run to preview which report artifact records match the defined retention policy. '  # noqa: E501
                'This does not delete files, S3 objects, or database rows.'
            ),
            'action_query': 'cleanup_dry_run=1',
            'default_retention_days': get_cleanup_dry_run_retention_days(),
            'max_items': 500,
        },
        'cleanup_dry_run_result': None,
        'notes': [
            'MVP2 storage configuration is read from ENV / config.py.',
            'Secrets should be provided through environment variables or Kubernetes Secrets.',
            'The UI is read-only for configuration; it only displays status and can run a verification check.',
            'Existing report records keep their backend prefix, so local and S3 artifacts can coexist.',
            'Retention is defined for MVP2. Cleanup remains dry-run/read-only unless destructive cleanup is explicitly enabled in configuration.',  # noqa: E501
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
) -> dict[str, Any]:
    backend_ready = False
    backend_label = 'Storage backend needs review'
    backend_description = 'The active storage backend is configured but needs verification.'

    if backend_name == 'local':
        backend_ready = bool(
            local_health.get(
                'root_writable',
                False,
            )
        )
        backend_label = 'Local storage ready' if backend_ready else 'Local storage needs review'
        backend_description = (
            'Local filesystem storage is writable and ready for generated report artifacts.'
            if backend_ready
            else 'Local filesystem storage is not writable. Review REPORT_LOCAL_STORAGE_DIR or filesystem permissions.'
        )
    elif backend_name == 's3':
        backend_ready = bool(
            s3_health.get(
                'configuration_complete',
                False,
            )
        )
        backend_label = 'S3 storage configured' if backend_ready else 'S3 storage incomplete'
        backend_description = (
            'S3-compatible storage has the minimum required bucket and dependency configuration.'
            if backend_ready
            else 'S3-compatible storage requires bucket configuration and boto3 availability before it can be trusted.'
        )

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

    if backend_name == 's3' and hasattr(
        backend,
        'test_connection',
    ):
        backend.test_connection()  # type: ignore[attr-defined]

    test_key = 'reports/storage-verification/kaori-report-storage-check.txt'

    with NamedTemporaryFile(
        mode='w',
        encoding='utf-8',
        suffix='.txt',
        delete=False,
    ) as temp_file:
        temp_file.write(
            'kaori report storage verification\n',
        )
        temp_path = Path(
            temp_file.name,
        )

    try:
        stored_file = backend.save_file(
            source_path=temp_path,
            object_key=test_key,
        )

        exists = backend.exists(
            stored_file.object_key,
        )

        backend.delete(
            stored_file.object_key,
        )

        return {
            'backend': backend_name,
            'uri': stored_file.uri,
            'object_key': stored_file.object_key,
            'size_bytes': stored_file.size_bytes,
            'exists_after_upload': exists,
            'verified': exists,
        }
    finally:
        temp_path.unlink(
            missing_ok=True,
        )


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
        except Exception as exc:
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
                        'error': str(
                            exc,
                        ),
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
        except Exception as exc:
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
                        error=str(
                            exc,
                        ),
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
