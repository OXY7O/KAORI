from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from celery.exceptions import CeleryError
from flask import current_app, request
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.alertmanager.resolver import resolve_alertmanager_sources
from app.analytics.materialization.catalog import canonical_parameters, get_dataset
from app.analytics.materialization.serialization import ClusterReference
from app.analytics.materialization.service import SnapshotResult, read_snapshot
from app.common.dependencies import (
    DependencyBlocker,
    alert_source_connection_blocker,
    alert_source_setup_blocker,
    cluster_required_blocker,
    prometheus_capability_blocker,
    prometheus_connection_blocker,
    prometheus_setup_blocker,
)
from app.extensions.db import db
from app.integrations.prometheus.capabilities import definition as capability_definition
from app.integrations.prometheus.scope import KUBERNETES_CLUSTER_SCOPE
from app.jobs.dispatcher import dispatch_registered_job
from app.jobs.service import JobQuotaExceeded
from app.models import Cluster
from app.prometheus.resolver import resolve_prometheus_sources

_UNUSABLE_OPERATIONAL_STATES = {
    'unhealthy',
    'ready_not_connected',
    'degraded_not_connected',
}


@dataclass(frozen=True, slots=True)
class MaterializedRequest:
    result: SnapshotResult
    cluster: ClusterReference | None
    parameters: dict[str, str]
    dispatched: bool
    dispatch_error: str | None = None
    dependency_blocker: DependencyBlocker | None = None


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
            environment=str(row.environment or ''),
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
    """Resolve an explicit cluster or prefer a ready implicit scope.

    An explicit selection remains authoritative so KAORI can display the
    blocker for that cluster. Without an explicit selection, the first cluster
    that can serve the requested analytics dataset becomes the default.
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


def _candidate_is_usable(candidate: Any | None) -> bool:
    return bool(
        candidate is not None
        and candidate.operational_state not in _UNUSABLE_OPERATIONAL_STATES
    )


def _prometheus_resolution(*, dataset_key: str, cluster_id: str):
    dataset = get_dataset(dataset_key)
    return resolve_prometheus_sources(
        scope_type=KUBERNETES_CLUSTER_SCOPE,
        scope_key=str(cluster_id),
        required_binding_capabilities=dataset.required_binding_capabilities,
        required_technical_capabilities=dataset.required_capabilities,
    )


def _alert_resolutions(*, cluster_id: str):
    alertmanager_resolution = resolve_alertmanager_sources(
        scope_type=KUBERNETES_CLUSTER_SCOPE,
        scope_key=str(cluster_id),
    )
    prometheus_resolution = resolve_prometheus_sources(
        scope_type=KUBERNETES_CLUSTER_SCOPE,
        scope_key=str(cluster_id),
        required_binding_capabilities=('metrics', 'alert_metrics'),
        required_technical_capabilities=('instant_query', 'kubernetes_identity'),
    )
    return alertmanager_resolution, prometheus_resolution


def _dataset_source_is_ready(
    *,
    dataset_key: str,
    cluster: ClusterReference,
    parameters: Mapping[str, str],
) -> bool:
    dataset = get_dataset(dataset_key)
    if dataset.source_kind == 'prometheus':
        resolution = _prometheus_resolution(
            dataset_key=dataset_key,
            cluster_id=cluster.id,
        )
        return _candidate_is_usable(resolution.selected)

    if dataset.source_kind == 'alert':
        source = str(parameters.get('source') or 'auto').strip().lower()
        alertmanager_resolution, prometheus_resolution = _alert_resolutions(
            cluster_id=cluster.id,
        )
        alertmanager_ready = _candidate_is_usable(alertmanager_resolution.selected)
        prometheus_ready = _candidate_is_usable(prometheus_resolution.selected)
        if source == 'alertmanager':
            return alertmanager_ready
        if source == 'prometheus':
            return prometheus_ready
        return alertmanager_ready or prometheus_ready

    return True


def selected_cluster_from_request(
    *,
    dataset_key: str | None = None,
    parameters: Mapping[str, str] | None = None,
) -> ClusterReference | None:
    raw_cluster_id = request.args.get('cluster_id', '').strip()
    clusters = _list_cluster_references()
    cluster_by_id = {cluster.id: cluster for cluster in clusters}

    if dataset_key is None:
        from app.prometheus.repository import resolve_instance_for_cluster

        readiness = lambda cluster_id: resolve_instance_for_cluster(cluster_id) is not None
    else:
        normalized = parameters or {}
        readiness = lambda cluster_id: _dataset_source_is_ready(
            dataset_key=dataset_key,
            cluster=cluster_by_id[cluster_id],
            parameters=normalized,
        )

    return choose_cluster_reference(
        raw_cluster_id=raw_cluster_id,
        clusters=clusters,
        is_analytics_ready=readiness,
    )


def _capability_labels(keys: tuple[str, ...]) -> list[str]:
    labels: list[str] = []
    for key in keys:
        capability = capability_definition(key)
        labels.append(
            capability.label
            if capability is not None
            else str(key).replace('_', ' ').title()
        )
    return labels


def _prometheus_dependency_blocker(
    *,
    dataset_key: str,
    cluster: ClusterReference,
) -> DependencyBlocker | None:
    dataset = get_dataset(dataset_key)
    resolution = _prometheus_resolution(
        dataset_key=dataset_key,
        cluster_id=cluster.id,
    )
    if not resolution.candidates:
        return prometheus_setup_blocker(cluster)

    selected = resolution.selected
    if selected is not None:
        if selected.operational_state in _UNUSABLE_OPERATIONAL_STATES:
            return prometheus_connection_blocker(
                cluster,
                detail=selected.decision_reason,
            )
        return None

    candidate = resolution.candidates[0]
    missing_capabilities = (
        *candidate.missing_binding_capabilities,
        *candidate.missing_technical_capabilities,
    )
    if missing_capabilities:
        return prometheus_capability_blocker(
            cluster,
            capability_labels=_capability_labels(missing_capabilities),
            feature_label=dataset.label,
        )
    return prometheus_connection_blocker(
        cluster,
        detail=candidate.decision_reason,
    )


def _alert_dependency_blocker(
    *,
    cluster: ClusterReference,
    selected_source: str,
) -> DependencyBlocker | None:
    source = (selected_source or 'auto').strip().lower()
    alertmanager_resolution, prometheus_resolution = _alert_resolutions(
        cluster_id=cluster.id,
    )

    def alertmanager_blocker() -> DependencyBlocker | None:
        selected = alertmanager_resolution.selected
        if _candidate_is_usable(selected):
            return None
        if not alertmanager_resolution.candidates:
            return alert_source_setup_blocker(cluster, source='alertmanager')
        candidate = selected or alertmanager_resolution.candidates[0]
        return alert_source_connection_blocker(
            cluster,
            source='alertmanager',
            detail=candidate.decision_reason,
        )

    def prometheus_blocker() -> DependencyBlocker | None:
        selected = prometheus_resolution.selected
        if _candidate_is_usable(selected):
            return None
        if not prometheus_resolution.candidates:
            return alert_source_setup_blocker(cluster, source='prometheus')
        candidate = selected or prometheus_resolution.candidates[0]
        missing_capabilities = (
            *candidate.missing_binding_capabilities,
            *candidate.missing_technical_capabilities,
        )
        if missing_capabilities:
            return prometheus_capability_blocker(
                cluster,
                capability_labels=_capability_labels(missing_capabilities),
                feature_label='Alerts & Anomalies',
            )
        return alert_source_connection_blocker(
            cluster,
            source='prometheus',
            detail=candidate.decision_reason,
        )

    if source == 'alertmanager':
        return alertmanager_blocker()
    if source == 'prometheus':
        return prometheus_blocker()

    alertmanager_issue = alertmanager_blocker()
    prometheus_issue = prometheus_blocker()
    if alertmanager_issue is None or prometheus_issue is None:
        return None
    if not alertmanager_resolution.candidates and not prometheus_resolution.candidates:
        return alert_source_setup_blocker(cluster, source='auto')

    details = [
        candidate.decision_reason
        for candidate in (
            alertmanager_resolution.candidates[0]
            if alertmanager_resolution.candidates
            else None,
            prometheus_resolution.candidates[0]
            if prometheus_resolution.candidates
            else None,
        )
        if candidate is not None
    ]
    return alert_source_connection_blocker(
        cluster,
        source='auto',
        detail=' '.join(details),
    )


def _dependency_blocker(
    *,
    dataset_key: str,
    cluster: ClusterReference,
    parameters: dict[str, str],
) -> DependencyBlocker | None:
    dataset = get_dataset(dataset_key)
    if dataset.source_kind == 'prometheus':
        return _prometheus_dependency_blocker(
            dataset_key=dataset_key,
            cluster=cluster,
        )
    if dataset.source_kind == 'alert':
        return _alert_dependency_blocker(
            cluster=cluster,
            selected_source=parameters.get('source', 'auto'),
        )
    return None


def resolve_materialized_request(
    *,
    dataset_key: str,
    job_key: str,
    parameters: dict[str, Any],
) -> MaterializedRequest:
    normalized = canonical_parameters(dataset_key, parameters)
    cluster = selected_cluster_from_request(
        dataset_key=dataset_key,
        parameters=normalized,
    )
    if cluster is None:
        return MaterializedRequest(
            SnapshotResult(None, None, 'missing', False),
            None,
            normalized,
            False,
            dependency_blocker=cluster_required_blocker(),
        )

    normalized['cluster_id'] = str(cluster.id)
    result = read_snapshot(
        cluster_id=cluster.id,
        dataset_key=dataset_key,
        parameters=normalized,
    )
    dependency_blocker = _dependency_blocker(
        dataset_key=dataset_key,
        cluster=cluster,
        parameters=normalized,
    )
    if dependency_blocker is not None:
        return MaterializedRequest(
            result,
            cluster,
            normalized,
            False,
            dependency_blocker=dependency_blocker,
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
            dispatch_error = (
                'Analytics preparation could not be queued. '
                'Retry after worker capacity is available.'
            )

    return MaterializedRequest(
        result,
        cluster,
        normalized,
        dispatched,
        dispatch_error,
        dependency_blocker,
    )
