from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from flask import current_app
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.models.job import JobExecution
from app.models.report import Report
from app.reports.catalog import OUTPUT_FORMAT_SPECS
from app.reports.storage.service import (
    build_report_download_path,
    build_report_storage_backend,
    parse_report_storage_uri,
)
from app.retention.policy_service import resolve_policy
from app.retention.types import ArchiveBoundary, ArchiveSupplement, PartialCleanupError, RetentionPolicy

_TERMINAL_REPORT_STATUSES = ('ready', 'failed', 'archived')
_ARTIFACT_REPORT_STATUSES = ('ready', 'archived')
_ACTIVE_JOB_STATUSES = ('queued', 'running', 'retrying', 'cancel_requested')


class GeneratedReportArchiveDomain:
    """Archive generated report metadata together with its binary artifact evidence."""

    name = 'generated_report'
    source_model = 'reports'
    schema_version = 1

    def build_policy(self) -> RetentionPolicy:
        retention_days = _positive_int_config('GENERATED_REPORT_RETENTION_DAYS', 90)
        archive_retention_days = _positive_int_config('GENERATED_REPORT_ARCHIVE_RETENTION_DAYS', 365)
        batch_size = max(100, min(_positive_int_config('GENERATED_REPORT_RETENTION_BATCH_SIZE', 250), 2500))
        failed_retention_days = _positive_int_config('GENERATED_REPORT_FAILED_RETENTION_DAYS', 30)
        archived_retention_days = _positive_int_config('GENERATED_REPORT_ARCHIVED_RETENTION_DAYS', 180)

        fallback = RetentionPolicy(
            domain=self.name,
            enabled=_bool_config('GENERATED_REPORT_RETENTION_ENABLED', False),
            retention_days=retention_days,
            archive_retention_days=archive_retention_days,
            batch_size=batch_size,
            settings={
                'failed_retention_days': failed_retention_days,
                'archived_retention_days': max(archived_retention_days, retention_days),
                'archive_binary_artifacts': True,
                'protect_active_generation': True,
            },
        )
        policy = resolve_policy(self.name, fallback)
        return replace(policy, batch_size=max(100, min(policy.batch_size, 2500)))

    def inspect_boundary(self, policy: RetentionPolicy) -> ArchiveBoundary:
        now = datetime.now(UTC)
        settings = dict(policy.settings or {})
        failed_days = max(int(settings.get('failed_retention_days') or 30), 1)
        archived_days = max(
            int(settings.get('archived_retention_days') or policy.retention_days),
            policy.retention_days,
        )
        cutoff_at = now - timedelta(days=min(policy.retention_days, failed_days, archived_days))
        eligible_filter = self._eligible_filter(policy, now=now)

        record_count, maximum_record_id, range_start, range_end = (
            db.session.query(
                func.count(Report.id),
                func.max(Report.id),
                func.min(Report.updated_at),
                func.max(Report.updated_at),
            )
            .filter(eligible_filter)
            .one()
        )

        protected_record_count = (
            db.session.query(func.count(Report.id)).filter(self._safety_hold_filter(policy, now=now)).scalar()
        )

        return ArchiveBoundary(
            selected_at=now,
            cutoff_at=cutoff_at,
            maximum_record_id=int(maximum_record_id) if maximum_record_id is not None else None,
            record_count=int(record_count or 0),
            range_start=_as_utc(range_start),
            range_end=_as_utc(range_end),
            protected_record_count=int(protected_record_count or 0),
        )

    def iter_records(self, boundary: ArchiveBoundary, policy: RetentionPolicy) -> Iterator[dict[str, Any]]:
        if boundary.maximum_record_id is None or boundary.record_count <= 0:
            return

        last_id = 0
        selection_now = boundary.selected_at
        while True:
            rows = (
                Report.query.filter(
                    self._eligible_filter(policy, now=selection_now),
                    Report.id <= boundary.maximum_record_id,
                    Report.id > last_id,
                )
                .order_by(Report.id.asc())
                .limit(policy.batch_size)
                .all()
            )
            if not rows:
                break

            for report in rows:
                last_id = report.id
                yield self._serialize(report)

            db.session.expire_all()

    def iter_supplements(
        self,
        boundary: ArchiveBoundary,
        policy: RetentionPolicy,
    ) -> Iterator[ArchiveSupplement]:
        if boundary.maximum_record_id is None or boundary.record_count <= 0:
            return

        selection_now = boundary.selected_at
        last_id = 0
        while True:
            rows = (
                Report.query.filter(
                    self._eligible_filter(policy, now=selection_now),
                    Report.id <= boundary.maximum_record_id,
                    Report.id > last_id,
                    Report.status.in_(_ARTIFACT_REPORT_STATUSES),
                )
                .order_by(Report.id.asc())
                .limit(policy.batch_size)
                .all()
            )
            if not rows:
                break

            for report in rows:
                last_id = report.id
                stored_path = str(report.file_path or '').strip()
                if not stored_path:
                    raise RuntimeError(f'Report {report.id} has no retained artifact reference.')

                backend_name, object_key = parse_report_storage_uri(stored_path)
                source_path = build_report_download_path(stored_path)
                if not source_path.is_file():
                    raise RuntimeError(f'Report {report.id} artifact is not available from {backend_name} storage.')

                format_spec = OUTPUT_FORMAT_SPECS.get(str(report.output_format or '').strip().lower())
                content_type = format_spec.mimetype if format_spec is not None else 'application/octet-stream'

                filename = Path(object_key).name or f'report-{report.id}.{report.output_format}'
                yield ArchiveSupplement(
                    record_id=report.id,
                    source_path=source_path,
                    relative_path=f'report-{report.id}/{filename}',
                    content_type=content_type,
                    metadata={
                        'original-uri': stored_path,
                        'report-status': report.status,
                        'report-type': report.report_type,
                        'output-format': report.output_format,
                    },
                )

            db.session.expire_all()

    def estimate_uncompressed_bytes(self, boundary: ArchiveBoundary, policy: RetentionPolicy) -> int:
        if boundary.maximum_record_id is None or boundary.record_count <= 0:
            return 0
        selection_now = boundary.selected_at
        artifact_bytes = (
            db.session.query(func.coalesce(func.sum(Report.file_size_bytes), 0))
            .filter(
                self._eligible_filter(policy, now=selection_now),
                Report.id <= boundary.maximum_record_id,
            )
            .scalar()
        )
        return int(artifact_bytes or 0) + (boundary.record_count * 1200)

    def cleanup_records(self, record_ids: Iterable[Any], policy: RetentionPolicy) -> int:
        deleted_total = 0
        now = datetime.now(UTC)

        try:
            for record_id in record_ids:
                report = Report.query.filter(
                    Report.id == int(record_id),
                    self._eligible_filter(policy, now=now),
                ).first()
                if report is None:
                    continue

                if report.status in _ARTIFACT_REPORT_STATUSES and report.file_path:
                    backend_name, object_key = parse_report_storage_uri(report.file_path)
                    build_report_storage_backend(backend_name).delete(object_key)

                db.session.delete(report)
                db.session.commit()
                deleted_total += 1
        except (OSError, RuntimeError, ValueError, SQLAlchemyError) as exc:
            db.session.rollback()
            raise PartialCleanupError(
                'Generated report cleanup stopped after one or more verified report records were removed.',
                deleted_total,
            ) from exc

        return deleted_total

    def _eligible_filter(self, policy: RetentionPolicy, *, now: datetime):
        status_filter = self._status_age_filter(policy, now=now)
        active_jobs = select(JobExecution.id).where(JobExecution.status.in_(_ACTIVE_JOB_STATUSES))
        return and_(
            status_filter,
            or_(Report.job_execution_id.is_(None), Report.job_execution_id.notin_(active_jobs)),
        )

    def _safety_hold_filter(self, policy: RetentionPolicy, *, now: datetime):
        aged_terminal = self._status_age_filter(policy, now=now, require_artifact_reference=False)
        active_jobs = select(JobExecution.id).where(JobExecution.status.in_(_ACTIVE_JOB_STATUSES))
        missing_artifact = and_(
            Report.status.in_(_ARTIFACT_REPORT_STATUSES),
            or_(Report.file_path.is_(None), Report.file_path == ''),
        )
        active_generation = and_(Report.job_execution_id.is_not(None), Report.job_execution_id.in_(active_jobs))
        return and_(aged_terminal, or_(missing_artifact, active_generation))

    def _status_age_filter(
        self,
        policy: RetentionPolicy,
        *,
        now: datetime,
        require_artifact_reference: bool = True,
    ):
        settings = dict(policy.settings or {})
        failed_days = max(int(settings.get('failed_retention_days') or 30), 1)
        archived_days = max(
            int(settings.get('archived_retention_days') or policy.retention_days),
            policy.retention_days,
        )

        ready_filter = and_(
            Report.status == 'ready',
            Report.updated_at < now - timedelta(days=policy.retention_days),
        )
        archived_filter = and_(
            Report.status == 'archived',
            Report.updated_at < now - timedelta(days=archived_days),
        )
        if require_artifact_reference:
            artifact_reference = and_(Report.file_path.is_not(None), Report.file_path != '')
            ready_filter = and_(ready_filter, artifact_reference)
            archived_filter = and_(archived_filter, artifact_reference)

        return or_(
            ready_filter,
            archived_filter,
            and_(Report.status == 'failed', Report.updated_at < now - timedelta(days=failed_days)),
        )

    def _serialize(self, report: Report) -> dict[str, Any]:
        return {
            'schema_version': self.schema_version,
            'domain': self.name,
            'source': {
                'model': self.source_model,
                'record_id': report.id,
            },
            'report': {
                'name': report.name,
                'report_type': report.report_type,
                'report_domain': report.report_domain,
                'source_kind': report.source_kind,
                'cluster_id': report.cluster_id,
                'namespace': report.namespace,
                'scope_asset_type': report.scope_asset_type,
                'scope_asset_id': report.scope_asset_id,
                'scope_asset_label_snapshot': report.scope_asset_label_snapshot,
                'period': report.period,
                'output_format': report.output_format,
                'status': report.status,
                'sections': report.sections_as_list(),
                'job_execution_id': report.job_execution_id,
                'generated_by_id': report.generated_by_id,
                'generated_by_username_snapshot': report.generated_by_username_snapshot,
                'generated_by_display_name_snapshot': report.generated_by_display_name_snapshot,
                'generated_by_auth_source_snapshot': report.generated_by_auth_source_snapshot,
                'file_path': report.file_path,
                'file_size_bytes': report.file_size_bytes,
                'error_message': report.error_message,
                'created_at': _isoformat(report.created_at),
                'updated_at': _isoformat(report.updated_at),
            },
        }


def _positive_int_config(key: str, default: int) -> int:
    try:
        return max(int(current_app.config.get(key, default)), 1)
    except (TypeError, ValueError):
        return default


def _bool_config(key: str, default: bool) -> bool:
    value = current_app.config.get(key, default)
    if isinstance(value, bool):
        return value
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'y', 'on'}


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _isoformat(value: datetime | None) -> str | None:
    normalized = _as_utc(value)
    return normalized.isoformat() if normalized is not None else None
