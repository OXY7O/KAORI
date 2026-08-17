from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from celery.exceptions import CeleryError
from flask import current_app, request
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.alertmanager.resolver import resolve_alertmanager_sources
from app.analytics.kubernetes.materialization.catalog import (
    canonical_parameters,
    get_dataset,
    source_binding_capabilities,
    source_technical_capabilities,
)
from app.analytics.kubernetes.materialization.serialization import ClusterReference
from app.analytics.kubernetes.materialization.service import SnapshotResult, read_snapshot
from app.common.dependencies import (
    DependencyBlocker,
    alert_source_connection_blocker,
    alert_source_setup_blocker,
    cluster_required_blocker,
    metrics_source_capability_blocker,
    metrics_source_connection_blocker,
    metrics_source_setup_blocker,
)
from app.extensions.db import db
from app.integrations.metrics.capabilities import definition as capability_definition
from app.integrations.metrics.scope import KUBERNETES_CLUSTER_SCOPE
from app.jobs.dispatcher import dispatch_registered_job
from app.jobs.service import JobQuotaExceeded
from app.metrics.resolver import resolve_metrics_sources
from app.models import Cluster

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
    source_warning: DependencyBlocker | None = None


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
    # Resolver selection already enforces enabled bindings, readiness, scope,
    # and query transport capabilities. Persisted runtime health is advisory:
    # a previous timeout must not suppress a fresh worker attempt.
    return candidate is not None


def _metrics_source_resolution(
    *,
    dataset_key: str,
    cluster_id: str,
    strict: bool = False,
):
    dataset = get_dataset(dataset_key)
    return resolve_metrics_sources(
        scope_type=KUBERNETES_CLUSTER_SCOPE,
        scope_key=str(cluster_id),
        required_binding_capabilities=(
            dataset.required_binding_capabilities if strict else source_binding_capabilities(dataset_key)
        ),
        required_technical_capabilities=(
            dataset.required_capabilities if strict else source_technical_capabilities(dataset_key)
        ),
    )


def _alert_resolutions(*, cluster_id: str):
    alertmanager_resolution = resolve_alertmanager_sources(
        scope_type=KUBERNETES_CLUSTER_SCOPE,
        scope_key=str(cluster_id),
    )
    metrics_source_resolution = resolve_metrics_sources(
        scope_type=KUBERNETES_CLUSTER_SCOPE,
        scope_key=str(cluster_id),
        required_binding_capabilities=('metrics',),
        required_technical_capabilities=('instant_query',),
    )
    return alertmanager_resolution, metrics_source_resolution


def _dataset_source_is_ready(
    *,
    dataset_key: str,
    cluster: ClusterReference,
    parameters: Mapping[str, str],
) -> bool:
    dataset = get_dataset(dataset_key)
    try:
        if dataset.source_kind == 'metrics_source':
            resolution = _metrics_source_resolution(
                dataset_key=dataset_key,
                cluster_id=cluster.id,
            )
            return _candidate_is_usable(resolution.selected)

        if dataset.source_kind == 'alert':
            source = str(parameters.get('source') or 'auto').strip().lower()
            alertmanager_resolution, metrics_source_resolution = _alert_resolutions(
                cluster_id=cluster.id,
            )
            alertmanager_ready = _candidate_is_usable(alertmanager_resolution.selected)
            metrics_source_ready = _candidate_is_usable(metrics_source_resolution.selected)
            if source == 'alertmanager':
                return alertmanager_ready
            if source == 'metrics_source':
                return metrics_source_ready
            return alertmanager_ready or metrics_source_ready
    except Exception as exc:
        current_app.logger.exception(
            'Could not evaluate analytics source readiness for %s on cluster %s.',
            dataset_key,
            cluster.id,
            extra={
                'dataset_key': dataset_key,
                'cluster_id': str(cluster.id),
                'error': str(exc)[:1000],
            },
        )
        return False

    return True


def _cluster_has_snapshot(
    *,
    dataset_key: str,
    cluster_id: str,
    parameters: Mapping[str, str],
) -> bool:
    normalized = canonical_parameters(
        dataset_key,
        {**parameters, 'cluster_id': cluster_id},
    )
    return read_snapshot(
        cluster_id=cluster_id,
        dataset_key=dataset_key,
        parameters=normalized,
    ).available


def selected_cluster_from_request(
    *,
    dataset_key: str | None = None,
    parameters: Mapping[str, str] | None = None,
) -> ClusterReference | None:
    raw_cluster_id = request.args.get('cluster_id', '').strip()
    clusters = _list_cluster_references()
    cluster_by_id = {cluster.id: cluster for cluster in clusters}

    if dataset_key is None:
        from app.metrics.repository import resolve_instance_for_cluster

        def readiness(cluster_id: str) -> bool:
            return resolve_instance_for_cluster(cluster_id) is not None
    else:
        normalized = parameters or {}

        def readiness(cluster_id: str) -> bool:
            return _cluster_has_snapshot(
                dataset_key=dataset_key,
                cluster_id=cluster_id,
                parameters=normalized,
            ) or _dataset_source_is_ready(
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
        labels.append(capability.label if capability is not None else str(key).replace('_', ' ').title())
    return labels


def _metrics_source_dependency_state(
    *,
    dataset_key: str,
    cluster: ClusterReference,
) -> tuple[DependencyBlocker | None, DependencyBlocker | None]:
    """Return a hard execution blocker and an optional readiness warning.

    A connected metrics source with instant/range query support is sufficient
    for the worker to attempt materialization. Missing high-level domain
    evidence remains visible as a warning, but does not suppress committed data
    or prevent the worker from collecting authoritative runtime evidence.
    """

    execution = _metrics_source_resolution(
        dataset_key=dataset_key,
        cluster_id=cluster.id,
        strict=False,
    )
    if not execution.candidates:
        return metrics_source_setup_blocker(cluster), None

    selected = execution.selected
    if selected is None:
        candidate = execution.candidates[0]
        missing_capabilities = (
            *candidate.missing_binding_capabilities,
            *candidate.missing_technical_capabilities,
        )
        if missing_capabilities:
            return (
                metrics_source_capability_blocker(
                    cluster,
                    capability_labels=_capability_labels(missing_capabilities),
                    feature_label=get_dataset(dataset_key).label,
                ),
                None,
            )
        return (
            metrics_source_connection_blocker(
                cluster,
                detail=candidate.decision_reason,
            ),
            None,
        )

    runtime_warning = None
    if selected.operational_state in _UNUSABLE_OPERATIONAL_STATES:
        runtime_warning = metrics_source_connection_blocker(
            cluster,
            detail=(
                'The previous runtime observation was degraded. KAORI will retry the '
                'dataset query because the binding and query transport remain eligible. '
                f'{selected.decision_reason}'
            ),
        )

    strict = _metrics_source_resolution(
        dataset_key=dataset_key,
        cluster_id=cluster.id,
        strict=True,
    )
    if strict.selected is not None:
        return None, runtime_warning

    candidate = strict.candidates[0] if strict.candidates else selected
    missing_capabilities = (
        *candidate.missing_binding_capabilities,
        *candidate.missing_technical_capabilities,
    )
    if not missing_capabilities:
        return None, runtime_warning

    capability_warning = metrics_source_capability_blocker(
        cluster,
        capability_labels=_capability_labels(missing_capabilities),
        feature_label=get_dataset(dataset_key).label,
    )
    return (
        None,
        capability_warning,
    )


def _alert_dependency_blocker(
    *,
    cluster: ClusterReference,
    selected_source: str,
) -> DependencyBlocker | None:
    source = (selected_source or 'auto').strip().lower()
    alertmanager_resolution, metrics_source_resolution = _alert_resolutions(
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

    def metrics_source_blocker() -> DependencyBlocker | None:
        selected = metrics_source_resolution.selected
        if _candidate_is_usable(selected):
            return None
        if not metrics_source_resolution.candidates:
            return alert_source_setup_blocker(cluster, source='metrics_source')
        candidate = selected or metrics_source_resolution.candidates[0]
        missing_capabilities = (
            *candidate.missing_binding_capabilities,
            *candidate.missing_technical_capabilities,
        )
        if missing_capabilities:
            return metrics_source_capability_blocker(
                cluster,
                capability_labels=_capability_labels(missing_capabilities),
                feature_label='Alerts & Anomalies',
            )
        return alert_source_connection_blocker(
            cluster,
            source='metrics_source',
            detail=candidate.decision_reason,
        )

    if source == 'alertmanager':
        return alertmanager_blocker()
    if source == 'metrics_source':
        return metrics_source_blocker()

    alertmanager_issue = alertmanager_blocker()
    metrics_source_issue = metrics_source_blocker()
    if alertmanager_issue is None or metrics_source_issue is None:
        return None
    if not alertmanager_resolution.candidates and not metrics_source_resolution.candidates:
        return alert_source_setup_blocker(cluster, source='auto')

    details = [
        candidate.decision_reason
        for candidate in (
            alertmanager_resolution.candidates[0] if alertmanager_resolution.candidates else None,
            metrics_source_resolution.candidates[0] if metrics_source_resolution.candidates else None,
        )
        if candidate is not None
    ]
    return alert_source_connection_blocker(
        cluster,
        source='auto',
        detail=' '.join(details),
    )


def _dependency_state(
    *,
    dataset_key: str,
    cluster: ClusterReference,
    parameters: dict[str, str],
) -> tuple[DependencyBlocker | None, DependencyBlocker | None]:
    dataset = get_dataset(dataset_key)
    if dataset.source_kind == 'metrics_source':
        return _metrics_source_dependency_state(
            dataset_key=dataset_key,
            cluster=cluster,
        )
    if dataset.source_kind == 'alert':
        return (
            _alert_dependency_blocker(
                cluster=cluster,
                selected_source=parameters.get('source', 'auto'),
            ),
            None,
        )
    return None, None


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
    try:
        dependency_blocker, source_warning = _dependency_state(
            dataset_key=dataset_key,
            cluster=cluster,
            parameters=normalized,
        )
    except Exception as exc:
        current_app.logger.exception(
            'Could not resolve analytics source dependency for %s on cluster %s.',
            dataset_key,
            cluster.id,
            extra={
                'dataset_key': dataset_key,
                'cluster_id': str(cluster.id),
                'error': str(exc)[:1000],
            },
        )
        dataset = get_dataset(dataset_key)
        dependency_blocker = (
            alert_source_connection_blocker(
                cluster,
                source=normalized.get('source', 'auto'),
                detail=f'Source readiness evaluation failed: {exc}',
            )
            if dataset.source_kind == 'alert'
            else metrics_source_connection_blocker(
                cluster,
                detail=f'Source readiness evaluation failed: {exc}',
            )
        )
        source_warning = None
    if dependency_blocker is not None and result.available:
        source_warning = dependency_blocker
        dependency_blocker = None
    if dependency_blocker is not None:
        return MaterializedRequest(
            result,
            cluster,
            normalized,
            False,
            dependency_blocker=dependency_blocker,
            source_warning=source_warning,
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
        ) as exc:
            db.session.rollback()
            current_app.logger.exception(
                'Could not queue analytics materialization %s for cluster %s.',
                dataset_key,
                cluster.id,
            )
            detail = str(exc).strip() or exc.__class__.__name__
            dispatch_error = (
                '[dispatch_failed] Analytics preparation could not be queued: '
                f'{detail} Recommended action: Review Redis/Celery availability, '
                'the selected integration binding, and the web log before retrying.'
            )

    return MaterializedRequest(
        result,
        cluster,
        normalized,
        dispatched,
        dispatch_error,
        dependency_blocker,
        source_warning,
    )
