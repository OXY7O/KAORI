from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.jobs.service import (
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


@dataclass
class JobExecutionContext:
    """Cooperative lifecycle helper for future analytics and forecasting tasks.

    Long-running tasks should call ``checkpoint`` between query chunks or model
    phases. This updates the canonical heartbeat and honors cancel requests without
    terminating the worker process abruptly.
    """

    task_id: str

    def start(self, *, message: str, total: int = 0) -> None:
        mark_job_running(self.task_id, message=message, total=total)

    def checkpoint(
        self,
        *,
        current: int | None = None,
        total: int | None = None,
        message: str | None = None,
    ) -> None:
        if is_cancel_requested(self.task_id):
            raise JobCancellationRequested('The job was canceled by an operator.')
        update_job_progress(
            self.task_id,
            current=current,
            total=total,
            message=message,
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
            self.task_id,
            result_summary=result_summary,
            result_type=result_type,
            result_reference=result_reference,
            partial=partial,
        )

    def fail(self, error: Exception | str, *, error_code: str | None = None) -> None:
        mark_job_failed(self.task_id, error=error, error_code=error_code)

    def retrying(self, *, message: str, error: Exception | str | None = None) -> None:
        mark_job_retrying(self.task_id, message=message, error=error)

    def canceled(self, *, message: str = 'Canceled at a cooperative checkpoint') -> None:
        mark_job_canceled(self.task_id, message=message)
