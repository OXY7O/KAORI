from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

from celery.exceptions import CeleryError
from flask import current_app, request
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.analytics.materialization.service import SnapshotResult, normalize_parameters, read_snapshot
from app.extensions.db import db
from app.jobs.dispatcher import dispatch_registered_job
from app.jobs.service import JobQuotaExceeded
from app.analytics.materialization.serialization import ClusterReference
from app.models import Cluster


@dataclass(frozen=True, slots=True)
class MaterializedRequest:
    result: SnapshotResult
    cluster: ClusterReference | None
    parameters: dict[str, str]
    dispatched: bool
    dispatch_error: str | None = None


def _list_cluster_references() -> list[ClusterReference]:
    rows = (
        Cluster.query.with_entities(
            Cluster.id,
            Cluster.name,
            Cluster.environment,
            Cluster.status,
            Cluster.created_at,
        )
        .order_by(Cluster.created_at.asc(), Cluster.id.asc())
        .all()
    )
    return [
        ClusterReference(
            id=str(row.id),
            name=str(row.name),
            environment=str(row.environment),
            status=str(row.status or 'unknown'),
        )
        for row in rows
    ]


def choose_cluster_reference(
    *,
    raw_cluster_id: str,
    clusters: list[ClusterReference],
    is_analytics_ready: Callable[[str], bool],
) -> ClusterReference | None:
    """Resolve an explicit cluster or prefer a ready default for analytics.

    An explicitly selected cluster is authoritative even when its Prometheus
    source is not ready, so KAORI can show the correct scoped blocker. When the
    URL has no cluster selection, prefer the first analytics-ready cluster
    instead of letting an unrelated unready cluster block every analytics page.
    """

    normalized = (raw_cluster_id or '').strip()
    if normalized:
        for cluster in clusters:
            if cluster.id == normalized:
                return cluster

    for cluster in clusters:
        if is_analytics_ready(cluster.id):
            return cluster

    return clusters[0] if clusters else None


def selected_cluster_from_request() -> ClusterReference | None:
    from app.prometheus.repository import resolve_instance_for_cluster

    raw_cluster_id = request.args.get('cluster_id', '').strip()
    clusters = _list_cluster_references()
    return choose_cluster_reference(
        raw_cluster_id=raw_cluster_id,
        clusters=clusters,
        is_analytics_ready=lambda cluster_id: resolve_instance_for_cluster(cluster_id) is not None,
    )


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
