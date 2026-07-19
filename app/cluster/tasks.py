from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from celery import shared_task

from app.cluster.individual_sync_state import store_individual_sync_metadata
from app.cluster.sync_state import (
    claim_cluster_sync_lock,
    mark_cluster_sync_completed,
    store_cluster_sync_metadata,
)
from app.extensions import db
from app.inventory.service import sync_inventory
from app.models import Cluster
from app.notifications.service import create_notification

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(
        UTC,
    ).isoformat()


def _build_result(
    *,
    requested_by_user_id: int,
    total_count: int,
    synced_count: int,
    failed_clusters: list[str],
    started_at: str,
    duration_seconds: float,
) -> dict[str, Any]:
    failed_count = len(
        failed_clusters,
    )
    finished_at = _now_iso()

    if failed_count == total_count:
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

    if failed_clusters:
        failed_preview = ', '.join(
            failed_clusters[:3],
        )
        if failed_count > 3:
            failed_preview = f'{failed_preview}, +{failed_count - 3} more'

        detail = (
            f'Failed clusters: {failed_preview}. Successful cluster inventory remains refreshed; '
            'review cluster access, TLS settings, and Kubernetes API compatibility.'
        )
    else:
        detail = (
            'Cluster metadata, nodes, namespaces, workloads, pods, services, ingress, '
            'and storage inventory are now refreshed.'
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
        'finished_at': finished_at,
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
    requested_by_user_id: int,
) -> dict[str, Any]:
    task_id = self.request.id
    started_timer = perf_counter()
    started_at = _now_iso()
    total_count = 0
    synced_count = 0
    failed_clusters: list[str] = []

    progress: dict[str, Any] = {
        'requested_by_user_id': requested_by_user_id,
        'created_at': started_at,
        'started_at': started_at,
        'total_count': total_count,
        'processed_count': 0,
        'synced_count': 0,
        'failed_count': 0,
        'current_cluster_name': None,
    }

    try:
        clusters = Cluster.query.order_by(
            Cluster.name.asc(),
        ).all()
        total_count = len(
            clusters,
        )
        progress['total_count'] = total_count

        if not claim_cluster_sync_lock(task_id):
            raise RuntimeError('Cluster synchronization lock is owned by another Celery task.')

        store_cluster_sync_metadata(
            task_id=task_id,
            metadata=progress,
        )
        self.update_state(
            state='PROGRESS',
            meta=progress,
        )

        for index, cluster in enumerate(
            clusters,
            start=1,
        ):
            progress.update(
                {
                    'processed_count': index - 1,
                    'synced_count': synced_count,
                    'failed_count': len(failed_clusters),
                    'current_cluster_name': cluster.name,
                    'heartbeat_at': _now_iso(),
                }
            )
            store_cluster_sync_metadata(
                task_id=task_id,
                metadata=progress,
            )
            if not claim_cluster_sync_lock(task_id):
                raise RuntimeError('Cluster synchronization lock ownership was lost.')
            self.update_state(
                state='PROGRESS',
                meta=progress,
            )

            try:
                sync_inventory(
                    cluster,
                )
                synced_count += 1
            except Exception:
                db.session.rollback()
                failed_clusters.append(
                    cluster.name,
                )
                logger.exception(
                    'Cluster inventory synchronization failed for %s.',
                    cluster.name,
                )

            progress.update(
                {
                    'processed_count': index,
                    'synced_count': synced_count,
                    'failed_count': len(failed_clusters),
                    'current_cluster_name': cluster.name,
                    'heartbeat_at': _now_iso(),
                }
            )
            store_cluster_sync_metadata(
                task_id=task_id,
                metadata=progress,
            )
            if not claim_cluster_sync_lock(task_id):
                raise RuntimeError('Cluster synchronization lock ownership was lost.')
            self.update_state(
                state='PROGRESS',
                meta=progress,
            )

        result = _build_result(
            requested_by_user_id=requested_by_user_id,
            total_count=total_count,
            synced_count=synced_count,
            failed_clusters=failed_clusters,
            started_at=started_at,
            duration_seconds=round(
                perf_counter() - started_timer,
                1,
            ),
        )

        create_notification(
            user_id=requested_by_user_id,
            event_type='kubernetes_inventory_sync',
            status=result['status'],
            title=result['title'],
            message=result['message'],
            detail=result['detail'],
            action_url='/clusters/',
            metadata={
                'task_id': task_id,
                'total_count': result['total_count'],
                'synced_count': result['synced_count'],
                'failed_count': result['failed_count'],
                'failed_clusters': result['failed_clusters'],
                'duration_seconds': result['duration_seconds'],
            },
        )
        store_cluster_sync_metadata(
            task_id=task_id,
            metadata=result,
        )
        mark_cluster_sync_completed(
            task_id,
        )

        return result
    except Exception as exc:
        db.session.rollback()
        logger.exception(
            'Unexpected failure while synchronizing all clusters.',
        )

        result = {
            'status': 'error',
            'title': 'Kubernetes sync interrupted',
            'message': 'The background synchronization stopped before all clusters were processed.',
            'detail': 'Review the Celery worker logs and Redis connectivity before retrying.',
            'total_count': total_count,
            'processed_count': progress.get('processed_count', 0),
            'synced_count': synced_count,
            'failed_count': len(failed_clusters),
            'failed_clusters': failed_clusters,
            'requested_by_user_id': requested_by_user_id,
            'started_at': started_at,
            'finished_at': _now_iso(),
            'duration_seconds': round(
                perf_counter() - started_timer,
                1,
            ),
            'current_cluster_name': progress.get('current_cluster_name'),
            'error_type': type(exc).__name__,
        }

        try:
            create_notification(
                user_id=requested_by_user_id,
                event_type='kubernetes_inventory_sync',
                status='error',
                title=result['title'],
                message=result['message'],
                detail=result['detail'],
                action_url='/clusters/',
                metadata={
                    'task_id': task_id,
                    'total_count': total_count,
                    'synced_count': synced_count,
                    'failed_count': len(failed_clusters),
                    'duration_seconds': result['duration_seconds'],
                },
            )
        except Exception:
            db.session.rollback()
            logger.exception(
                'Could not persist the cluster synchronization failure notification.',
            )

        store_cluster_sync_metadata(
            task_id=task_id,
            metadata=result,
        )
        mark_cluster_sync_completed(
            task_id,
        )

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
    requested_by_user_id: int,
) -> dict[str, Any]:
    task_id = self.request.id
    started_timer = perf_counter()
    started_at = _now_iso()
    cluster = Cluster.query.get(cluster_id)
    cluster_name = cluster.name if cluster is not None else 'Unknown cluster'
    progress = {
        'cluster_id': cluster_id,
        'cluster_name': cluster_name,
        'requested_by_user_id': requested_by_user_id,
        'created_at': started_at,
        'started_at': started_at,
        'status': 'info',
        'title': 'Cluster inventory sync in progress',
        'message': f'Synchronizing Kubernetes inventory for {cluster_name}.',
    }
    store_individual_sync_metadata(task_id=task_id, metadata=progress)
    self.update_state(state='PROGRESS', meta=progress)

    try:
        if cluster is None:
            raise LookupError('The selected Kubernetes cluster no longer exists.')
        sync_inventory(cluster)
        result = {
            **progress,
            'status': 'success',
            'title': 'Cluster inventory synchronized',
            'message': f'{cluster_name} inventory was refreshed successfully.',
            'detail': 'Cluster metadata, nodes, namespaces, workloads, pods, services, ingress, and storage snapshots are now up to date.',
            'finished_at': _now_iso(),
            'duration_seconds': round(perf_counter() - started_timer, 1),
        }
    except Exception as exc:
        db.session.rollback()
        logger.exception('Inventory synchronization failed for cluster %s.', cluster_id)
        result = {
            **progress,
            'status': 'error',
            'title': 'Cluster inventory sync failed',
            'message': f'{cluster_name} inventory could not be refreshed.',
            'detail': 'Review Kubernetes API compatibility, cluster credentials, TLS settings, and KAORI logs before retrying.',
            'finished_at': _now_iso(),
            'duration_seconds': round(perf_counter() - started_timer, 1),
            'error_type': type(exc).__name__,
        }

    create_notification(
        user_id=requested_by_user_id,
        event_type='kubernetes_inventory_sync',
        status=result['status'],
        title=result['title'],
        message=result['message'],
        detail=result['detail'],
        action_url='/clusters/',
        metadata={
            'task_id': task_id,
            'cluster_id': cluster_id,
            'cluster_name': cluster_name,
            'scope': 'single_cluster',
            'duration_seconds': result['duration_seconds'],
        },
    )
    store_individual_sync_metadata(task_id=task_id, metadata=result)
    return result
