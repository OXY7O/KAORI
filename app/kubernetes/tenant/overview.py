from __future__ import annotations

from typing import Any

from celery.exceptions import CeleryError
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.platform_operations.jobs.dispatcher import JobWorkerUnavailable, dispatch_registered_job
from app.platform_operations.jobs.service import JobQuotaExceeded

_INVENTORY_JOB_KEY = 'kubernetes.inventory.sync'


def dispatch_tenant_inventory_sync(*, requested_by_user_id: int) -> dict[str, Any]:
    """Dispatch the canonical Kubernetes Inventory job for the Tenant Overview."""

    metadata: dict[str, Any] = {
        'operation': 'tenant_inventory_sync',
        'job_key': _INVENTORY_JOB_KEY,
    }
    try:
        outcome = dispatch_registered_job(
            job_key=_INVENTORY_JOB_KEY,
            trigger_type='manual',
            requested_by_user_id=requested_by_user_id,
        )
    except ValueError as exc:
        return {
            'event_type': 'kubernetes_tenant_inventory_sync_blocked',
            'status': 'warning',
            'title': 'Tenant Inventory Sync Could Not Start',
            'message': str(exc),
            'metadata': metadata,
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
            'event_type': 'kubernetes_tenant_inventory_sync_failed',
            'status': 'error',
            'title': 'Tenant Inventory Sync Could Not Start',
            'message': 'KAORI could not queue the canonical Kubernetes inventory synchronization.',
            'detail': f'{type(exc).__name__}: {str(exc)[:500]}',
            'metadata': metadata,
        }

    if not outcome.accepted:
        return {
            'event_type': 'kubernetes_tenant_inventory_sync_blocked',
            'status': 'warning',
            'title': 'Tenant Inventory Sync Blocked',
            'message': outcome.message,
            'metadata': {**metadata, 'dispatch_status': outcome.status},
        }

    job = outcome.job
    return {
        'event_type': 'kubernetes_tenant_inventory_sync_dispatched',
        'status': 'success' if outcome.created else 'info',
        'title': 'Tenant Inventory Sync Queued' if outcome.created else 'Tenant Inventory Sync Already Active',
        'message': outcome.message,
        'detail': ('Tenant Overview will read the committed Kubernetes inventory evidence after collection completes.'),
        'metadata': {
            **metadata,
            'job_public_id': job.public_id if job is not None else None,
            'created': outcome.created,
        },
    }
