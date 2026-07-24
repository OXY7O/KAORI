from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from celery.exceptions import CeleryError
from flask import current_app, request
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.analytics.materialization.service import SnapshotResult, normalize_parameters, read_snapshot
from app.extensions.db import db
from app.jobs.dispatcher import dispatch_registered_job
from app.jobs.service import JobQuotaExceeded
from app.models import Cluster


@dataclass(frozen=True, slots=True)
class MaterializedRequest:
    result: SnapshotResult
    cluster: Cluster | None
    parameters: dict[str, str]
    dispatched: bool
    dispatch_error: str | None = None


def selected_cluster_from_request() -> Cluster | None:
    raw_cluster_id = request.args.get('cluster_id', '').strip()
    if raw_cluster_id.isdigit():
        cluster = Cluster.query.get(int(raw_cluster_id))
        if cluster is not None:
            return cluster
    return Cluster.query.order_by(Cluster.created_at.asc(), Cluster.id.asc()).first()


def resolve_materialized_request(
    *,
    dataset_key: str,
    job_key: str,
    parameters: dict[str, Any],
) -> MaterializedRequest:
    cluster = selected_cluster_from_request()
    normalized = normalize_parameters(parameters)
    if cluster is None:
        return MaterializedRequest(SnapshotResult(None, None, 'missing', False), None, normalized, False)

    normalized['cluster_id'] = str(cluster.id)
    result = read_snapshot(
        cluster_id=cluster.id,
        dataset_key=dataset_key,
        parameters=normalized,
    )
    dispatched = False
    dispatch_error = None
    if not result.available or result.stale:
        try:
            outcome = dispatch_registered_job(
                job_key=job_key,
                trigger_type='on_demand',
                requested_by_user_id=None,
                parameters={
                    'cluster_id': cluster.id,
                    'dataset_key': dataset_key,
                    'snapshot_parameters': normalized,
                },
            )
            dispatched = outcome.accepted
            if not outcome.accepted:
                dispatch_error = outcome.message
        except JobQuotaExceeded as exc:
            dispatch_error = str(exc)
        except (
            CeleryError,
            KombuOperationalError,
            LookupError,
            OSError,
            RuntimeError,
            SQLAlchemyError,
            ValueError,
        ):
            db.session.rollback()
            current_app.logger.exception(
                'Could not queue analytics materialization %s for cluster %s.',
                dataset_key,
                cluster.id,
            )
            dispatch_error = 'Analytics preparation could not be queued. Retry after worker capacity is available.'
    return MaterializedRequest(result, cluster, normalized, dispatched, dispatch_error)
