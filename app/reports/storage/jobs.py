from __future__ import annotations

from celery.exceptions import CeleryError
from flask import current_app
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.platform_operations.jobs.definitions.base import RegisteredJobDispatchResult
from app.platform_operations.jobs.dispatcher import JobDispatchOptions, enqueue_canonical_job
from app.reports.storage.service import get_configured_storage_backend_name
from app.reports.storage.state import get_storage_config_fingerprint
from app.reports.storage.tasks import verify_report_storage_task

JOB_TYPE = 'report_storage'
OPERATION = 'verify_backend'


class ReportStorageVerificationEnqueueError(RuntimeError):
    """Raised when KAORI cannot register or dispatch strong storage verification."""


def get_report_storage_verification_queue_name() -> str:
    configured = current_app.config.get('REPORT_STORAGE_HEALTH_CELERY_QUEUE', 'maintenance')
    return str(configured or 'maintenance').strip() or 'maintenance'


def enqueue_report_storage_verification(*, requested_by_user_id: int | None) -> RegisteredJobDispatchResult:
    backend_name = get_configured_storage_backend_name()
    config_fingerprint = get_storage_config_fingerprint(backend_name)
    payload = {
        'backend': backend_name,
        'config_fingerprint': config_fingerprint,
        'verification_mode': 'write_confirm_delete',
        'trigger_type': 'manual',
    }

    try:
        job, created = enqueue_canonical_job(
            task=verify_report_storage_task,
            task_kwargs={
                'backend_name': backend_name,
                'config_fingerprint': config_fingerprint,
                'requested_by_user_id': requested_by_user_id,
            },
            job_type='report_storage',
            operation='verify_backend',
            queue_name=get_report_storage_verification_queue_name(),
            workload_class='standard',
            requested_by_user_id=requested_by_user_id,
            scope_type='report_storage_backend',
            scope_key=backend_name,
            resource_group=f'report-storage:{backend_name}',
            parameters=payload,
            payload=payload,
            max_attempts=1,
            dispatch_options=JobDispatchOptions(
                soft_time_limit_seconds=90,
                hard_time_limit_seconds=120,
                require_registered_worker=True,
            ),
        )
    except (CeleryError, KombuOperationalError, OSError, RuntimeError, SQLAlchemyError) as exc:
        db.session.rollback()
        raise ReportStorageVerificationEnqueueError(
            'KAORI could not enqueue the report storage verification worker job.'
        ) from exc

    return RegisteredJobDispatchResult(
        status='queued' if created else 'reused',
        message=(
            'Strong report storage verification was queued.'
            if created
            else 'Strong report storage verification is already active.'
        ),
        job=job,
        created=created,
    )
