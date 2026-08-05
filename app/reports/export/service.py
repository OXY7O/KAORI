from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from flask import current_app

from app.extensions.db import db
from app.models.report import Report
from app.reports.catalog import ReportContractError, validate_report_instance
from app.reports.export.artifacts import get_report_artifact_format
from app.reports.export.formatting import slugify
from app.reports.reference import report_reference_filename
from app.reports.storage.naming import build_report_object_key
from app.reports.storage.service import (
    build_report_download_path,
    report_file_exists,
    save_report_file,
)


def generate_report_artifact(
    report_id: int,
) -> tuple[bool, str]:
    """Render and persist one report through its configured artifact renderer."""

    report = db.session.get(Report, report_id)
    if report is None:
        return False, 'Report not found.'

    previous_status = report.status
    previous_file_path = report.file_path
    previous_file_size_bytes = report.file_size_bytes
    previous_artifact_available = bool(previous_file_path) and report_file_exists(previous_file_path)

    staging_path: Path | None = None
    artifact_format = None

    try:
        validate_report_instance(report)
        artifact_format = get_report_artifact_format(report.output_format)
        report.status = 'generating'
        report.error_message = None
        db.session.commit()

        staging_path = build_report_output_path(report)
        artifact_format.renderer(report, staging_path)

        object_key = build_report_object_key(report)
        stored_file = save_report_file(
            source_path=staging_path,
            object_key=object_key,
            content_type=artifact_format.mimetype,
        )

        report.file_path = stored_file.uri
        report.file_size_bytes = stored_file.size_bytes
        report.status = 'ready'
        report.error_message = None
        db.session.commit()

        if previous_status == 'ready' and previous_artifact_available:
            return (
                True,
                (
                    f'{artifact_format.label} report regenerated successfully. '
                    'The previous artifact is retained until cleanup policy is enabled.'
                ),
            )

        return True, f'{artifact_format.label} report generated successfully.'

    except Exception as exc:
        is_contract_error = isinstance(exc, ReportContractError)
        artifact_label = artifact_format.label if artifact_format is not None else 'report'
        if is_contract_error:
            current_app.logger.warning(
                'Report contract rejected generation for report %s: %s',
                report_id,
                exc,
            )
        else:
            current_app.logger.exception(
                '%s generation failed for report %s.',
                artifact_label,
                report_id,
            )
        db.session.rollback()

        failed_report = db.session.get(Report, report_id)
        failure_detail = (
            str(exc)
            if is_contract_error
            else (
                f'KAORI could not generate the {artifact_label} artifact. '
                'Review report scope, source readiness, storage readiness, and worker logs before retrying.'
            )
        )
        retained_artifact = previous_status == 'ready' and previous_artifact_available

        if failed_report is not None:
            if retained_artifact:
                failed_report.status = 'ready'
                failed_report.file_path = previous_file_path
                failed_report.file_size_bytes = previous_file_size_bytes
                failed_report.error_message = (
                    'Regeneration failed. The existing ready artifact was retained. '
                    f'{failure_detail}'
                )
            else:
                failed_report.status = 'failed'
                failed_report.error_message = failure_detail
            db.session.commit()

        if retained_artifact:
            return False, f'Regeneration failed. The existing artifact was retained. {failure_detail}'
        return False, failure_detail

    finally:
        if staging_path is not None and staging_path.exists():
            staging_path.unlink(missing_ok=True)


def get_download_file_path(
    report_id: int,
) -> tuple[bool, str, Path | None]:
    report = db.session.get(Report, report_id)
    if report is None:
        return False, 'Report not found.', None
    if report.status not in ['ready', 'archived']:
        return False, 'Report is not ready or archived for download.', None
    if not report.file_path:
        return False, 'Report file path is not available.', None

    try:
        if not report_file_exists(report.file_path):
            return False, 'Report file does not exist in configured storage.', None
        file_path = build_report_download_path(report.file_path)
    except Exception:
        current_app.logger.warning('Unable to access report artifact for download.', exc_info=True)
        return (
            False,
            'Report storage is temporarily unavailable. Restore storage connectivity and try again.',
            None,
        )

    if not file_path.exists():
        return False, 'Report file is not available for download.', None
    return True, 'Report file is ready.', file_path


def build_report_output_path(report: Report) -> Path:
    staging_dir = get_report_staging_dir()
    staging_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime('%Y%m%d%H%M%S')
    safe_name = slugify(report.name)
    reference = report_reference_filename(report)
    extension = get_report_artifact_format(report.output_format).extension
    return staging_dir / f'{reference}-{safe_name}-{timestamp}{extension}'


def get_report_staging_dir() -> Path:
    configured_path = current_app.config.get('REPORT_RENDER_STAGING_DIR')
    if configured_path:
        staging_dir = Path(configured_path)
        if not staging_dir.is_absolute():
            staging_dir = Path(current_app.root_path).parent / staging_dir
        return staging_dir
    return Path(current_app.instance_path) / 'report-render-staging'
