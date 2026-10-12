from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from app.extensions.db import db
from app.models.job import JobPolicy
from app.models.report import ReportSchedule

def get_automation_posture(
    storage_context: dict[str, Any],
    worker_context: dict[str, Any],
) -> dict[str, str]:
    storage_ready = bool(storage_context.get('ready', False))
    worker_tone = str(worker_context.get('tone') or 'unknown')
    worker_ready = worker_tone == 'normal'

    if not storage_ready:
        return {
            'status_label': 'Execution Needs Review',
            'status_tone': 'warning',
            'title': 'Artifact Execution Paused',
            'description': (
                'Schedule definitions remain available for management, but Run Now and unattended '
                'generation stay paused until artifact storage is writable.'
            ),
            'execution_label': 'Paused',
            'execution_tone': 'warning',
        }

    if not worker_ready:
        return {
            'status_label': 'Dispatcher Needs Review',
            'status_tone': worker_tone if worker_tone in {'warning', 'critical', 'unknown'} else 'warning',
            'title': 'Dispatcher Needs Attention',
            'description': (
                'Artifact storage is writable, but unattended execution depends on a healthy Reports '
                'worker consuming the dedicated queue.'
            ),
            'execution_label': 'Needs Review',
            'execution_tone': worker_tone if worker_tone in {'warning', 'critical', 'unknown'} else 'warning',
        }

    dispatcher_enabled = db.session.scalar(
        select(JobPolicy.enabled).where(JobPolicy.job_key == 'reports.schedule.dispatch')
    )
    if not dispatcher_enabled:
        return {
            'status_label': 'Dispatcher Disabled',
            'status_tone': 'warning',
            'title': 'Automatic Dispatch Is Disabled',
            'description': 'Enable the Report Schedule Dispatcher in Job Configuration before unattended reporting.',
            'execution_label': 'Disabled',
            'execution_tone': 'warning',
        }

    enabled_schedules = db.session.scalar(
        select(func.count(ReportSchedule.id)).where(ReportSchedule.is_enabled.is_(True))
    ) or 0
    if not enabled_schedules:
        return {
            'status_label': 'Waiting For Schedule',
            'status_tone': 'warning',
            'title': 'No Active Report Schedules',
            'description': 'Create or enable at least one recurring definition before unattended reporting.',
            'execution_label': 'Waiting',
            'execution_tone': 'warning',
        }

    return {
        'status_label': 'Automation Ready',
        'status_tone': 'normal',
        'title': 'Ready for Unattended Execution',
        'description': (
            'Schedule definitions, the Reports worker, and artifact storage are ready for Run Now '
            'and recurring report execution.'
        ),
        'execution_label': 'Ready',
        'execution_tone': 'normal',
    }


