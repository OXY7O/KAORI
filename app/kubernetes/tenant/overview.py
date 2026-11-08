from __future__ import annotations

from typing import Any

from celery.exceptions import CeleryError
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.platform_operations.jobs.dispatcher import JobWorkerUnavailable, dispatch_registered_job
from app.platform_operations.jobs.service import JobQuotaExceeded

_INVENTORY_JOB_KEY = 'kubernetes.tenant.sync'


def dispatch_tenant_inventory_sync(*, requested_by_user_id: int) -> dict[str, Any]:
    """Dispatch Tenant sync without creating a success notification at click time."""

    try:
        outcome = dispatch_registered_job(
            job_key=_INVENTORY_JOB_KEY,
            trigger_type='manual',
            requested_by_user_id=requested_by_user_id,
        )
    except ValueError as exc:
        return {
            'accepted': False,
            'event_type': 'kubernetes_tenant_inventory_sync_blocked',
            'status': 'warning',
            'title': 'Tenant Sync Could Not Start',
            'message': str(exc),
            'metadata': {'operation': 'tenant_inventory_sync', 'job_key': _INVENTORY_JOB_KEY},
        }
    except (
        JobWorkerUnavailable,
        JobQuotaExceeded,
        CeleryError,
        KombuOperationalError,
        OSError,
        RuntimeError,
        SQLAlchemyError,
    ) as exc:
        return {
            'accepted': False,
            'event_type': 'kubernetes_tenant_inventory_sync_failed',
            'status': 'error',
            'title': 'Tenant Sync Could Not Start',
            'message': 'KAORI could not dispatch Tenant synchronization to the inventory worker.',
            'detail': 'Verify PostgreSQL, Redis, Celery Beat, and the inventory worker before retrying.',
            'metadata': {
                'operation': 'tenant_inventory_sync',
                'job_key': _INVENTORY_JOB_KEY,
                'error_type': type(exc).__name__,
            },
        }

    if not outcome.accepted or outcome.job is None:
        return {
            'accepted': False,
            'event_type': 'kubernetes_tenant_inventory_sync_blocked',
            'status': 'warning',
            'title': 'Tenant Sync Blocked',
            'message': outcome.message,
            'metadata': {
                'operation': 'tenant_inventory_sync',
                'job_key': _INVENTORY_JOB_KEY,
                'dispatch_status': outcome.status,
            },
        }

    return {
        'accepted': True,
        'created': outcome.created,
        'job': outcome.job,
        'job_public_id': outcome.job.public_id,
        'message': outcome.message,
    }
