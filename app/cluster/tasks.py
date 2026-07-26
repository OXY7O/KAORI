from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from celery import shared_task

from app.cluster.individual_sync_state import store_individual_sync_metadata
from app.cluster.sync_state import mark_cluster_sync_completed, store_cluster_sync_metadata
from app.extensions.db import db
from app.integrations.kubernetes.resolver import connection_for_cluster
from app.integrations.registry import get_integration
from app.jobs.execution import JobExecutionContext
from app.models import Cluster
from app.notifications.service import create_notification

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _store_global(task_id: str, payload: dict[str, Any]) -> None:
    try:
        store_cluster_sync_metadata(task_id=task_id, metadata=payload)
    except Exception:
        logger.exception('Could not persist supplemental global inventory-sync metadata.')


def _store_single(task_id: str, payload: dict[str, Any]) -> None:
    try:
        store_individual_sync_metadata(task_id=task_id, metadata=payload)
    except Exception:
        logger.exception('Could not persist supplemental cluster inventory-sync metadata.')


def _build_result(
    *,
    requested_by_user_id: int | None,
    total_count: int,
    synced_count: int,
    failed_clusters: list[str],
    started_at: str,
    duration_seconds: float,
) -> dict[str, Any]:
    failed_count = len(failed_clusters)
    if failed_count == total_count and total_count:
        status = 'error'
        title = 'Kubernetes sync failed'
        message = f'All {total_count} registered clusters failed to synchronize.'
    elif failed_count:
        status = 'warning'
        title = 'Sync completed with warnings'
        message = f'{synced_count} clusters synced and {failed_count} failed.'
    else:
        status = 'success'
        title = 'Kubernetes sync completed'
        message = f'All {synced_count} registered clusters synchronized successfully.'
    failed_preview = ', '.join(failed_clusters[:3])
    if failed_count > 3:
        failed_preview = f'{failed_preview}, +{failed_count - 3} more'
    detail = (
        f'Failed clusters: {failed_preview}. Successful cluster inventory remains refreshed; '
        'review cluster access, TLS settings, and Kubernetes API compatibility.'
        if failed_clusters
        else 'Cluster metadata, nodes, namespaces, workloads, pods, services, ingress, and storage inventory are now refreshed.'
    )
    return {
        'status': status,
        'title': title,
        'message': message,
        'detail': detail,
        'total_count': total_count,
        'processed_count': total_count,
        'synced_count': synced_count,
        'failed_count': failed_count,
        'failed_clusters': failed_clusters,
        'requested_by_user_id': requested_by_user_id,
        'started_at': started_at,
        'finished_at': _now_iso(),
        'duration_seconds': duration_seconds,
        'current_cluster_name': None,
    }


@shared_task(
    bind=True,
    name='app.cluster.tasks.sync_all_clusters',
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_all_clusters_task(
    self,
    *,
    requested_by_user_id: int | None,
    targets: list[dict[str, str]] | None = None,
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    task_id = str(self.request.id)
    context = JobExecutionContext(task_id, job_execution_id)
    started_timer = perf_counter()
    started_at = _now_iso()
    if targets is None:
        targets = [
            {'cluster_id': str(cluster.id), 'cluster_name': cluster.name}
            for cluster in Cluster.query.order_by(Cluster.name.asc(), Cluster.id.asc()).all()
        ]
    total_count = len(targets)
    synced_count = 0
    failed_clusters: list[str] = []
    failure_evidence: list[dict[str, str]] = []
    context.start(message='Synchronizing Kubernetes inventory for all registered clusters.', total=total_count)

    try:
        for index, target in enumerate(targets, start=1):
            cluster_id = str(target['cluster_id'])
            cluster_name = target['cluster_name']
            context.checkpoint(
                current=index - 1,
                total=total_count,
                message=f'Synchronizing {cluster_name}.',
            )
            progress = {
                'requested_by_user_id': requested_by_user_id,
                'job_execution_id': job_execution_id,
                'created_at': started_at,
                'started_at': started_at,
                'total_count': total_count,
                'processed_count': index - 1,
                'synced_count': synced_count,
                'failed_count': len(failed_clusters),
                'current_cluster_name': cluster_name,
                'heartbeat_at': _now_iso(),
            }
            _store_global(task_id, progress)
            self.update_state(state='PROGRESS', meta=progress)
            try:
                cluster = db.session.get(Cluster, cluster_id)
                if cluster is None:
                    raise LookupError('The cluster was deleted after the fleet job was admitted.')
                connection = connection_for_cluster(cluster)
                get_integration('kubernetes').execute('inventory.sync', connection)
                synced_count += 1
            except Exception as exc:
                db.session.rollback()
                failed_clusters.append(cluster_name)
                failure_evidence.append(
                    {
                        'cluster_id': cluster_id,
                        'cluster_name': cluster_name,
                        'error_type': type(exc).__name__,
                        'message': str(exc),
                    }
                )
                logger.exception('Cluster inventory synchronization failed for %s.', cluster_name)

            context.checkpoint(
                current=index,
                total=total_count,
                message=(
                    f'Synchronized {cluster_name}.'
                    if cluster_name not in failed_clusters
                    else f'Finished {cluster_name} with an error.'
                ),
            )

        result = _build_result(
            requested_by_user_id=requested_by_user_id,
            total_count=total_count,
            synced_count=synced_count,
            failed_clusters=failed_clusters,
            started_at=started_at,
            duration_seconds=round(perf_counter() - started_timer, 1),
        )
        result['failure_evidence'] = failure_evidence
        if requested_by_user_id is not None:
            create_notification(
                user_id=requested_by_user_id,
                event_type='kubernetes_inventory_sync',
                status=result['status'],
                title=result['title'],
                message=result['message'],
                detail=result['detail'],
                action_url='/integrations/kubernetes',
                metadata={
                    'task_id': task_id,
                    'job_execution_id': job_execution_id,
                    'total_count': total_count,
                    'synced_count': synced_count,
                    'failed_count': len(failed_clusters),
                    'failed_clusters': failed_clusters,
                    'failure_evidence': failure_evidence,
                    'duration_seconds': result['duration_seconds'],
                },
            )
        context.succeed(
            result_summary=result,
            result_type='kubernetes_inventory_sync',
            partial=bool(failed_clusters),
        )
        _store_global(task_id, result)
        try:
            mark_cluster_sync_completed(task_id)
        except Exception:
            logger.exception('Could not expire supplemental global inventory-sync lock metadata.')
        return result
    except Exception as exc:
        db.session.rollback()
        context.fail(exc, error_code='kubernetes_inventory_sync_failed')
        logger.exception('Unexpected failure while synchronizing all clusters.')
        result = {
            'status': 'error',
            'title': 'Kubernetes sync interrupted',
            'message': 'The background synchronization stopped before all clusters were processed.',
            'detail': 'Review the inventory worker and Kubernetes integration evidence before retrying.',
            'total_count': total_count,
            'processed_count': synced_count + len(failed_clusters),
            'synced_count': synced_count,
            'failed_count': len(failed_clusters),
            'failed_clusters': failed_clusters,
            'failure_evidence': failure_evidence,
            'requested_by_user_id': requested_by_user_id,
            'started_at': started_at,
            'finished_at': _now_iso(),
            'duration_seconds': round(perf_counter() - started_timer, 1),
            'current_cluster_name': None,
            'error_type': type(exc).__name__,
        }
        _store_global(task_id, result)
        return result


@shared_task(
    bind=True,
    name='app.cluster.tasks.sync_single_cluster',
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_single_cluster_task(
    self,
    *,
    cluster_id: str,
    requested_by_user_id: int | None,
    job_execution_id: int | None = None,
) -> dict[str, Any]:
    task_id = str(self.request.id)
    context = JobExecutionContext(task_id, job_execution_id)
    started_timer = perf_counter()
    started_at = _now_iso()
    cluster = db.session.get(Cluster, cluster_id)
    cluster_name = cluster.name if cluster is not None else 'Unknown cluster'
    progress = {
        'cluster_id': cluster_id,
        'cluster_name': cluster_name,
        'requested_by_user_id': requested_by_user_id,
        'job_execution_id': job_execution_id,
        'created_at': started_at,
        'started_at': started_at,
        'status': 'info',
        'title': 'Cluster inventory sync in progress',
        'message': f'Synchronizing Kubernetes inventory for {cluster_name}.',
    }
    context.start(message=progress['message'], total=1)
    context.checkpoint(current=0, total=1, message=progress['message'])
    _store_single(task_id, progress)
    self.update_state(state='PROGRESS', meta=progress)

    try:
        if cluster is None:
            raise LookupError('The selected Kubernetes cluster no longer exists.')
        connection = connection_for_cluster(cluster)
        get_integration('kubernetes').execute('inventory.sync', connection)
        result = {
            **progress,
            'status': 'success',
            'title': 'Cluster inventory synchronized',
            'message': f'{cluster_name} inventory was refreshed successfully.',
            'detail': 'Cluster metadata, nodes, namespaces, workloads, pods, services, ingress, and storage snapshots are now up to date.',
            'finished_at': _now_iso(),
            'duration_seconds': round(perf_counter() - started_timer, 1),
        }
        context.succeed(result_summary=result, result_type='kubernetes_inventory_sync')
    except Exception as exc:
        db.session.rollback()
        context.fail(exc, error_code='kubernetes_inventory_sync_failed')
        logger.exception('Inventory synchronization failed for cluster %s.', cluster_id)
        result = {
            **progress,
            'status': 'error',
            'title': 'Cluster inventory sync failed',
            'message': f'{cluster_name} inventory could not be refreshed.',
            'detail': 'Review Kubernetes API compatibility, connection credentials, TLS settings, and KAORI logs before retrying.',
            'finished_at': _now_iso(),
            'duration_seconds': round(perf_counter() - started_timer, 1),
            'error_type': type(exc).__name__,
        }

    if requested_by_user_id is not None:
        create_notification(
            user_id=requested_by_user_id,
            event_type='kubernetes_inventory_sync',
            status=result['status'],
            title=result['title'],
            message=result['message'],
            detail=result['detail'],
            action_url='/integrations/kubernetes',
            metadata={
                'task_id': task_id,
                'job_execution_id': job_execution_id,
                'cluster_id': cluster_id,
                'cluster_name': cluster_name,
                'scope': 'single_cluster',
                'duration_seconds': result['duration_seconds'],
            },
        )
    _store_single(task_id, result)
    return result
