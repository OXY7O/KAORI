from __future__ import annotations

import logging

from flask import abort, redirect, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.integrations.deletion import DeletionBlocked
from app.kubernetes.cluster.service import delete_cluster, get_cluster_by_id, rollback_cluster_deletion
from app.platform_operations.notifications.service import record_operational_activity

logger = logging.getLogger(__name__)


def delete_cluster_response(cluster_id: str) -> ResponseReturnValue:
    cluster = get_cluster_by_id(cluster_id)
    if cluster is None:
        abort(404)

    cluster_name = cluster.name
    cluster_environment = cluster.environment
    connection = cluster.kubernetes_connection
    cluster_server = connection.server if connection is not None else None

    try:
        deletion_summary = delete_cluster(cluster)
    except DeletionBlocked as exc:
        rollback_cluster_deletion()
        record_operational_activity(
            user_id=current_user.id,
            event_type='cluster_delete_rejected',
            status='warning',
            title='Cluster deletion blocked',
            message=f'{cluster_name} still has active operational dependencies.',
            detail=str(exc),
            action_url=url_for('integrations.kubernetes_detail', cluster_id=cluster_id) + '#inventory',
            action_label='Review cluster lifecycle',
            action_icon='shield-alert',
            metadata={
                'cluster_id': cluster_id,
                'cluster_name': cluster_name,
                'active_jobs': exc.guard.active_jobs,
                'active_secret_reveal_requests': exc.guard.active_requests,
            },
            queue_feedback=True,
        )
        return redirect(url_for('integrations.kubernetes_detail', cluster_id=cluster_id) + '#inventory')
    except Exception as exc:
        rollback_cluster_deletion()
        logger.exception('Cluster deletion failed for %s.', cluster_id)
        record_operational_activity(
            user_id=current_user.id,
            event_type='cluster_delete',
            status='error',
            title='Cluster deletion failed',
            message=f'{cluster_name} could not be deleted.',
            detail='The database rejected the delete operation. Review dependent records and application logs before retrying.',
            action_url=url_for('integrations.kubernetes'),
            action_label='View clusters',
            action_icon='server',
            metadata={
                'cluster_id': cluster_id,
                'cluster_name': cluster_name,
                'reason': type(exc).__name__,
            },
            queue_feedback=True,
        )
    else:
        record_operational_activity(
            user_id=current_user.id,
            event_type='cluster_delete',
            status='success',
            title='Cluster deleted',
            message=f'{cluster_name} was removed from KAORI.',
            detail='Stored cluster registration, inventory, and associated observability configuration were removed according to database relationships.',
            action_url=url_for('integrations.kubernetes'),
            action_label='View clusters',
            action_icon='server',
            metadata={
                'cluster_id': cluster_id,
                'cluster_name': cluster_name,
                'environment': cluster_environment,
                'server': cluster_server,
                **deletion_summary,
            },
            queue_feedback=True,
        )

    return redirect(url_for('integrations.kubernetes'))
