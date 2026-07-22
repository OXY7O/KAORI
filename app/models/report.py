from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


def utc_now() -> datetime:
    return datetime.now(
        UTC,
    )


class Report(db.Model):
    __tablename__ = 'reports'

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        db.String(255),
        nullable=False,
        index=True,
    )

    report_type: Mapped[str] = mapped_column(
        db.String(100),
        nullable=False,
        index=True,
    )

    report_domain: Mapped[str] = mapped_column(
        db.String(50),
        nullable=False,
        default='kubernetes',
        index=True,
    )

    source_kind: Mapped[str] = mapped_column(
        db.String(50),
        nullable=False,
        default='kubernetes',
        index=True,
    )

    cluster_id: Mapped[str | None] = mapped_column(
        db.ForeignKey('clusters.id'),
        nullable=True,
        index=True,
    )

    namespace: Mapped[str | None] = mapped_column(
        db.String(255),
        nullable=True,
        index=True,
    )

    period: Mapped[str] = mapped_column(
        db.String(50),
        nullable=False,
        default='30d',
    )

    output_format: Mapped[str] = mapped_column(
        db.String(50),
        nullable=False,
        default='pdf',
    )

    status: Mapped[str] = mapped_column(
        db.String(50),
        nullable=False,
        default='requested',
        index=True,
    )

    sections: Mapped[list[str]] = mapped_column(
        db.JSON,
        nullable=False,
        default=list,
    )

    generated_by_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    generated_by_username_snapshot: Mapped[str | None] = mapped_column(
        db.String(100),
        nullable=True,
    )

    generated_by_display_name_snapshot: Mapped[str | None] = mapped_column(
        db.String(150),
        nullable=True,
    )

    generated_by_auth_source_snapshot: Mapped[str | None] = mapped_column(
        db.String(50),
        nullable=True,
    )

    file_path: Mapped[str | None] = mapped_column(
        db.String(500),
        nullable=True,
    )

    file_size_bytes: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        db.Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    def sections_as_list(self) -> list[str]:
        if isinstance(
            self.sections,
            list,
        ):
            return self.sections

        return []

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'report_type': self.report_type,
            'report_domain': self.report_domain,
            'source_kind': self.source_kind,
            'cluster_id': self.cluster_id,
            'namespace': self.namespace,
            'period': self.period,
            'output_format': self.output_format,
            'status': self.status,
            'sections': self.sections_as_list(),
            'generated_by_id': self.generated_by_id,
            'generated_by_username_snapshot': self.generated_by_username_snapshot,
            'generated_by_display_name_snapshot': self.generated_by_display_name_snapshot,
            'generated_by_auth_source_snapshot': self.generated_by_auth_source_snapshot,
            'file_path': self.file_path,
            'file_size_bytes': self.file_size_bytes,
            'error_message': self.error_message,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }


class ReportTemplate(db.Model):
    __tablename__ = 'report_templates'

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        db.String(255),
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        db.Text,
        nullable=True,
    )

    report_type: Mapped[str] = mapped_column(
        db.String(100),
        nullable=False,
        index=True,
    )

    report_domain: Mapped[str] = mapped_column(
        db.String(50),
        nullable=False,
        default='kubernetes',
        index=True,
    )

    source_kind: Mapped[str] = mapped_column(
        db.String(50),
        nullable=False,
        default='kubernetes',
        index=True,
    )

    status: Mapped[str] = mapped_column(
        db.String(50),
        nullable=False,
        default='draft',
        index=True,
    )

    output_format: Mapped[str] = mapped_column(
        db.String(50),
        nullable=False,
        default='pdf',
    )

    sections: Mapped[list[str]] = mapped_column(
        db.JSON,
        nullable=False,
        default=list,
    )

    source_template_key: Mapped[str | None] = mapped_column(
        db.String(150),
        nullable=True,
        index=True,
    )

    created_by_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    created_by_username_snapshot: Mapped[str | None] = mapped_column(
        db.String(100),
        nullable=True,
    )

    created_by_display_name_snapshot: Mapped[str | None] = mapped_column(
        db.String(150),
        nullable=True,
    )

    created_by_auth_source_snapshot: Mapped[str | None] = mapped_column(
        db.String(50),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    def sections_as_list(self) -> list[str]:
        if isinstance(self.sections, list):
            return self.sections
        return []

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'report_type': self.report_type,
            'report_domain': self.report_domain,
            'source_kind': self.source_kind,
            'status': self.status,
            'output_format': self.output_format,
            'sections': self.sections_as_list(),
            'source_template_key': self.source_template_key,
            'created_by_id': self.created_by_id,
            'created_by_username_snapshot': self.created_by_username_snapshot,
            'created_by_display_name_snapshot': self.created_by_display_name_snapshot,
            'created_by_auth_source_snapshot': self.created_by_auth_source_snapshot,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }


class ReportSchedule(db.Model):
    __tablename__ = 'report_schedules'

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        db.String(255),
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        db.Text,
        nullable=True,
    )

    report_type: Mapped[str] = mapped_column(
        db.String(100),
        nullable=False,
        index=True,
    )

    report_domain: Mapped[str] = mapped_column(
        db.String(50),
        nullable=False,
        default='kubernetes',
        index=True,
    )

    source_kind: Mapped[str] = mapped_column(
        db.String(50),
        nullable=False,
        default='kubernetes',
        index=True,
    )

    cluster_id: Mapped[str | None] = mapped_column(
        db.ForeignKey('clusters.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    namespace: Mapped[str | None] = mapped_column(
        db.String(255),
        nullable=True,
        index=True,
    )

    period: Mapped[str] = mapped_column(
        db.String(50),
        nullable=False,
        default='30d',
    )

    output_format: Mapped[str] = mapped_column(
        db.String(50),
        nullable=False,
        default='pdf',
    )

    sections: Mapped[list[str]] = mapped_column(
        db.JSON,
        nullable=False,
        default=list,
    )

    cadence: Mapped[str] = mapped_column(
        db.String(50),
        nullable=False,
        default='weekly',
        index=True,
    )

    run_time: Mapped[str] = mapped_column(
        db.String(5),
        nullable=False,
        default='08:00',
    )

    day_of_week: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    day_of_month: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    timezone: Mapped[str] = mapped_column(
        db.String(80),
        nullable=False,
        default='Asia/Jakarta',
    )

    is_enabled: Mapped[bool] = mapped_column(
        db.Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    next_run_at: Mapped[datetime | None] = mapped_column(
        db.DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    last_run_at: Mapped[datetime | None] = mapped_column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    last_status: Mapped[str | None] = mapped_column(
        db.String(50),
        nullable=True,
        index=True,
    )

    last_report_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('reports.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    created_by_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    created_by_username_snapshot: Mapped[str | None] = mapped_column(
        db.String(100),
        nullable=True,
    )

    created_by_display_name_snapshot: Mapped[str | None] = mapped_column(
        db.String(150),
        nullable=True,
    )

    created_by_auth_source_snapshot: Mapped[str | None] = mapped_column(
        db.String(50),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    def sections_as_list(self) -> list[str]:
        if isinstance(self.sections, list):
            return self.sections
        return []

    @property
    def status(self) -> str:
        return 'active' if self.is_enabled else 'paused'

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'report_type': self.report_type,
            'report_domain': self.report_domain,
            'source_kind': self.source_kind,
            'cluster_id': self.cluster_id,
            'namespace': self.namespace,
            'period': self.period,
            'output_format': self.output_format,
            'sections': self.sections_as_list(),
            'cadence': self.cadence,
            'run_time': self.run_time,
            'day_of_week': self.day_of_week,
            'day_of_month': self.day_of_month,
            'timezone': self.timezone,
            'is_enabled': self.is_enabled,
            'next_run_at': self.next_run_at,
            'last_run_at': self.last_run_at,
            'last_status': self.last_status,
            'last_report_id': self.last_report_id,
            'created_by_id': self.created_by_id,
            'created_by_username_snapshot': self.created_by_username_snapshot,
            'created_by_display_name_snapshot': self.created_by_display_name_snapshot,
            'created_by_auth_source_snapshot': self.created_by_auth_source_snapshot,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }


class ReportScheduleRun(db.Model):
    __tablename__ = 'report_schedule_runs'

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    schedule_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('report_schedules.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    report_id: Mapped[int | None] = mapped_column(
        db.ForeignKey('reports.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        db.String(50),
        nullable=False,
        default='started',
        index=True,
    )

    trigger_source: Mapped[str] = mapped_column(
        db.String(50),
        nullable=False,
        default='scheduler',
        index=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        db.Text,
        nullable=True,
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'schedule_id': self.schedule_id,
            'report_id': self.report_id,
            'status': self.status,
            'trigger_source': self.trigger_source,
            'started_at': self.started_at,
            'finished_at': self.finished_at,
            'error_message': self.error_message,
        }
