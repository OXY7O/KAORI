from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from app.extensions.db import db
from app.models.job import JobExecution
from app.platform_operations.jobs.execution import JobExecutionContext
from app.platform_operations.jobs.service import subscriber_user_ids
from app.platform_operations.notifications.service import record_operational_activity
from app.reports.storage.service import (
    clear_report_storage_status_cache,
    get_configured_storage_backend_name,
    refresh_report_storage_readiness,
    verify_active_report_storage,
)
from app.reports.storage.state import get_storage_config_fingerprint

logger = logging.getLogger(__name__)


class ReportStorageVerificationIncomplete(RuntimeError):
    """Raised when strong verification runs but cannot confirm the temporary object."""


class ReportStorageConfigurationChanged(RuntimeError):
    """Raised when the queued verification no longer matches active storage config."""


def _failure_evidence(error: Exception) -> dict[str, str]:
    error_name = type(error).__name__
    normalized = error_name.lower()
    if 'readtimeout' in normalized or normalized == 'timeouterror':
        return {
            'failure_class': 'read_timeout',
            'title': 'Report Storage Verification Failed',
            'message': 'The storage endpoint timed out during strong verification.',
            'detail': 'The worker did not receive the storage response within the configured read timeout.',
        }
    if 'connecttimeout' in normalized or 'endpointconnection' in normalized or 'connectionerror' in normalized:
        return {
            'failure_class': 'connection_failure',
            'title': 'Report Storage Verification Failed',
            'message': 'The storage endpoint could not be reached during strong verification.',
            'detail': (
                'Review endpoint reachability, DNS, TLS, reverse proxy, and network connectivity from the worker.'
            ),
        }
    if 'clienterror' in normalized:
        return {
            'failure_class': 'provider_rejected',
            'title': 'Report Storage Verification Failed',
            'message': 'The storage provider rejected the strong verification operation.',
            'detail': (
                'Review bucket access and the configured storage identity without exposing credentials in KAORI.'
            ),
        }
    if isinstance(error, ReportStorageVerificationIncomplete):
        return {
            'failure_class': 'verification_incomplete',
            'title': 'Report Storage Verification Incomplete',
            'message': 'KAORI could not confirm the temporary verification object.',
            'detail': 'The write path ran, but the worker could not confirm the verification object before cleanup.',
        }
    return {
        'failure_class': 'provider_error',
        'title': 'Report Storage Verification Failed',
        'message': 'The storage backend did not complete strong verification.',
        'detail': 'Review the report-storage worker log for provider-level technical evidence.',
    }


def _store_verification_evidence(
    *,
    job_execution_id: int | None,
    evidence: dict[str, Any],
) -> None:
    if job_execution_id is None:
        return
    job = db.session.get(JobExecution, job_execution_id)
    if job is None:
        return
    payload = dict(job.payload_json or {})
    payload['verification_evidence'] = dict(evidence)
    job.payload_json = payload
    db.session.commit()


def _record_storage_verification_completion(
    *,
    requested_by_user_id: int | None,
    job_execution_id: int | None,
    backend_name: str,
    success: bool,
    evidence: dict[str, Any],
) -> None:
    job = db.session.get(JobExecution, job_execution_id) if job_execution_id is not None else None
    user_ids = subscriber_user_ids(job) if job is not None else []
    if requested_by_user_id is not None and requested_by_user_id not in user_ids:
        user_ids.insert(0, requested_by_user_id)
    if not user_ids:
        return

    for user_id in user_ids:
        record_operational_activity(
            user_id=user_id,
            event_type='report_storage_verification_completed' if success else 'report_storage_verification_failed',
            status='success' if success else 'error',
            title=(
                'Report Storage Verified'
                if success
                else str(evidence.get('title') or 'Report Storage Verification Failed')
            ),
            message=(
                f'KAORI verified the {backend_name} report storage backend.'
                if success
                else str(evidence.get('message') or 'The report storage backend did not complete strong verification.')
            ),
            detail=(
                'The worker completed write, confirm, and cleanup verification on the active backend.'
                if success
                else str(evidence.get('detail') or 'Review the report-storage worker log for technical evidence.')
            ),
            action_url='/reports/storage?workspace=integrity',
            action_label='View storage',
            action_icon='hard-drive',
            metadata={
                'feedback_delivery': 'activity_center',
                'backend': backend_name,
                'verified': success,
                'job_execution_id': job_execution_id,
                'job_public_id': job.public_id if job is not None else None,
                'failure_class': evidence.get('failure_class'),
            },
            queue_feedback=False,
        )


@shared_task(
    name='app.reports.storage.tasks.refresh_report_storage_readiness_task',
    acks_late=False,
)
def refresh_report_storage_readiness_task() -> dict[str, Any]:
    """Refresh the shared report-storage readiness snapshot from a worker."""

    return refresh_report_storage_readiness(source='periodic')


@shared_task(
    bind=True,
    name='app.reports.storage.tasks.verify_report_storage_task',
    acks_late=True,
    reject_on_worker_lost=True,
)
def verify_report_storage_task(
    self,
    *,
    backend_name: str,
    config_fingerprint: str,
    requested_by_user_id: int | None,
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    """Run strong write → confirm → delete verification in the storage worker."""

    lifecycle = JobExecutionContext(str(self.request.id), job_execution_id)
    lifecycle.start(
        message='Preparing strong report storage verification.',
        total=3,
        percent=10,
        stage='Preparing Storage Verification',
        target=backend_name.upper(),
    )

    current_backend = get_configured_storage_backend_name()
    current_fingerprint = get_storage_config_fingerprint(current_backend)
    if current_backend != backend_name or current_fingerprint != config_fingerprint:
        evidence = {
            'failure_class': 'configuration_changed',
            'title': 'Report Storage Verification Canceled',
            'message': 'The report storage configuration changed before the worker started.',
            'detail': 'Run Verify Storage again so the worker uses the current backend configuration.',
        }
        _store_verification_evidence(job_execution_id=job_execution_id, evidence=evidence)
        public_detail = evidence['detail']
        lifecycle.fail(public_detail, error_code='report_storage_verification_configuration_changed')
        _record_storage_verification_completion(
            requested_by_user_id=requested_by_user_id,
            job_execution_id=job_execution_id,
            backend_name=current_backend,
            success=False,
            evidence=evidence,
        )
        raise ReportStorageConfigurationChanged(public_detail)

    lifecycle.checkpoint(
        current=1,
        total=3,
        percent=30,
        stage='Connecting to Storage',
        target=backend_name.upper(),
        message='Connecting to the active report storage backend from the worker.',
    )

    try:
        clear_report_storage_status_cache()
        lifecycle.checkpoint(
            current=2,
            total=3,
            percent=60,
            stage='Verifying Write Path',
            target=backend_name.upper(),
            message='Writing and confirming the temporary verification object.',
        )
        result = verify_active_report_storage()
        if not bool(result.get('verified')):
            raise ReportStorageVerificationIncomplete('Strong verification could not confirm the temporary object.')
    except Exception as exc:
        logger.exception('Report storage verification worker failed.')
        evidence = _failure_evidence(exc)
        _store_verification_evidence(job_execution_id=job_execution_id, evidence=evidence)
        public_detail = evidence['detail']
        lifecycle.fail(public_detail, error_code='report_storage_verification_failed')
        _record_storage_verification_completion(
            requested_by_user_id=requested_by_user_id,
            job_execution_id=job_execution_id,
            backend_name=backend_name,
            success=False,
            evidence=evidence,
        )
        raise

    lifecycle.checkpoint(
        current=3,
        total=3,
        percent=95,
        stage='Committing Verification Result',
        target=backend_name.upper(),
        message='Publishing the verified report storage readiness state.',
    )
    summary = {
        'backend': backend_name,
        'verified': True,
        'verification_mode': 'write_confirm_delete',
        'size_bytes': int(result.get('size_bytes') or 0),
        'exists_after_upload': bool(result.get('exists_after_upload')),
    }
    _store_verification_evidence(
        job_execution_id=job_execution_id,
        evidence={'failure_class': None, 'verified': True},
    )
    lifecycle.succeed(
        result_type='report_storage_verification',
        result_reference=str(result.get('uri') or ''),
        result_summary=summary,
    )
    _record_storage_verification_completion(
        requested_by_user_id=requested_by_user_id,
        job_execution_id=job_execution_id,
        backend_name=backend_name,
        success=True,
        evidence={'verified': True},
    )
    return {'status': 'healthy', **summary}
