from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.extensions.db import db
from app.platform_operations.jobs.service import (
    is_cancel_requested,
    mark_job_canceled,
    mark_job_failed,
    mark_job_retrying,
    mark_job_running,
    mark_job_succeeded,
    update_job_progress,
)


class JobCancellationRequested(RuntimeError):
    pass


class JobExecutionUnavailable(RuntimeError):
    pass


@dataclass
class JobExecutionContext:
    """Cooperative lifecycle helper for future analytics and forecasting tasks.

    Long-running tasks should call ``checkpoint`` between query chunks or model
    phases. This updates the canonical heartbeat and honors cancel requests without
    terminating the worker process abruptly.
    """

    task_id: str
    job_execution_id: int | None = None

    def _task_id(self) -> str:
        if self.job_execution_id is None:
            return self.task_id
        from app.models.job import JobExecution

        job = db.session.get(JobExecution, self.job_execution_id)
        if job is None or not job.celery_task_id:
            return self.task_id
        return str(job.celery_task_id)

    def start(
        self,
        *,
        message: str,
        total: int = 0,
        percent: int = 0,
        stage: str | None = None,
        target: str | None = None,
    ) -> None:
        job = mark_job_running(
            self._task_id(),
            message=message,
            total=total,
            percent=percent,
            stage=stage,
            target=target,
        )
        if job is not None and job.is_terminal:
            raise JobExecutionUnavailable(
                f'Canonical job {job.public_id} is already terminal with status {job.status}.'
            )

    def checkpoint(
        self,
        *,
        current: int | None = None,
        total: int | None = None,
        message: str | None = None,
        percent: int | None = None,
        stage: str | None = None,
        target: str | None = None,
    ) -> None:
        if is_cancel_requested(self._task_id()):
            raise JobCancellationRequested('The job was canceled by an operator.')
        update_job_progress(
            self._task_id(),
            current=current,
            total=total,
            message=message,
            percent=percent,
            stage=stage,
            target=target,
        )

    def succeed(
        self,
        *,
        result_summary: dict[str, Any] | None = None,
        result_type: str | None = None,
        result_reference: str | None = None,
        partial: bool = False,
    ) -> None:
        mark_job_succeeded(
            self._task_id(),
            result_summary=result_summary,
            result_type=result_type,
            result_reference=result_reference,
            partial=partial,
        )

    def fail(self, error: Exception | str, *, error_code: str | None = None) -> None:
        mark_job_failed(self._task_id(), error=error, error_code=error_code)

    def retrying(self, *, message: str, error: Exception | str | None = None) -> None:
        mark_job_retrying(self._task_id(), message=message, error=error)

    def canceled(self, *, message: str = 'Canceled at a cooperative checkpoint') -> None:
        mark_job_canceled(self._task_id(), message=message)
