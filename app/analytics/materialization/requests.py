from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from celery.exceptions import CeleryError
from flask import current_app, request
from kombu.exceptions import OperationalError as KombuOperationalError
from sqlalchemy.exc import SQLAlchemyError

from app.alertmanager.consumer import KUBERNETES_CLUSTER_SCOPE
from app.alertmanager.resolver import resolve_alertmanager_sources
from app.analytics.materialization.catalog import canonical_parameters, get_dataset
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
from app.jobs.dispatcher import dispatch_registered_job
from app.jobs.service import JobQuotaExceeded
from app.models import Cluster
from app.prometheus.resolver import resolve_prometheus_sources


@dataclass(frozen=True, slots=True)
class MaterializedRequest:
    result: SnapshotResult
    cluster: Cluster | None
    parameters: dict[str, str]
    dispatched: bool
    dispatch_error: str | None = None
    dependency_blocker: DependencyBlocker | None = None


def selected_cluster_from_request() -> Cluster | None:
    raw_cluster_id = request.args.get('cluster_id', '').strip()
    if raw_cluster_id:
        cluster = Cluster.query.get(raw_cluster_id)
        if cluster is not None:
            return cluster
    return Cluster.query.order_by(Cluster.created_at.asc(), Cluster.id.asc()).first()


def _prometheus_dependency_blocker(
    *,
    dataset_key: str,
    cluster: Cluster,
) -> DependencyBlocker | None:
    dataset = get_dataset(dataset_key)
    resolution = resolve_prometheus_sources(
        scope_type=KUBERNETES_CLUSTER_SCOPE,
        scope_key=str(cluster.id),
        required_binding_capabilities=dataset.required_binding_capabilities,
        required_technical_capabilities=dataset.required_capabilities,
    )
    if not resolution.candidates:
        return prometheus_setup_blocker(cluster)
    if resolution.selected is not None:
        if resolution.selected.operational_state in {
            'unhealthy',
            'ready_not_connected',
            'degraded_not_connected',
        }:
            return prometheus_connection_blocker(
                cluster,
                detail=resolution.selected.decision_reason,
            )
        return None
    candidate = resolution.candidates[0]
    missing_capabilities = (
        *candidate.missing_binding_capabilities,
        *candidate.missing_technical_capabilities,
    )
    if missing_capabilities:
        labels = []
        for key in missing_capabilities:
            capability = capability_definition(key)
            labels.append(
                capability.label
                if capability
                else str(key).replace('_', ' ').title()
            )
        return prometheus_capability_blocker(
            cluster,
            capability_labels=labels,
            feature_label=dataset.label,
        )
    return prometheus_connection_blocker(cluster, detail=candidate.decision_reason)


def _alert_dependency_blocker(
    *,
    cluster: Cluster,
    selected_source: str,
) -> DependencyBlocker | None:
    source = (selected_source or 'auto').strip().lower()
    alertmanager_resolution = resolve_alertmanager_sources(
        scope_type=KUBERNETES_CLUSTER_SCOPE,
        scope_key=str(cluster.id),
    )
    prometheus_resolution = resolve_prometheus_sources(
        scope_type=KUBERNETES_CLUSTER_SCOPE,
        scope_key=str(cluster.id),
        required_binding_capabilities=('metrics', 'alert_metrics'),
        required_technical_capabilities=('instant_query', 'kubernetes_identity'),
    )

    def alertmanager_blocker() -> DependencyBlocker | None:
        selected = alertmanager_resolution.selected
        if selected is not None and selected.operational_state not in {
            'unhealthy',
            'ready_not_connected',
            'degraded_not_connected',
        }:
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
        if selected is not None and selected.operational_state not in {
            'unhealthy',
            'ready_not_connected',
            'degraded_not_connected',
        }:
            return None
        if not prometheus_resolution.candidates:
            return alert_source_setup_blocker(cluster, source='prometheus')
        candidate = selected or prometheus_resolution.candidates[0]
        missing_capabilities = (
            *candidate.missing_binding_capabilities,
            *candidate.missing_technical_capabilities,
        )
        if missing_capabilities:
            labels = []
            for key in missing_capabilities:
                capability = capability_definition(key)
                labels.append(
                    capability.label
                    if capability
                    else str(key).replace('_', ' ').title()
                )
            return prometheus_capability_blocker(
                cluster,
                capability_labels=labels,
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

    if alertmanager_blocker() is None or prometheus_blocker() is None:
        return None
    if not alertmanager_resolution.candidates and not prometheus_resolution.candidates:
        return alert_source_setup_blocker(cluster, source='auto')
    details = [
        candidate.decision_reason
        for candidate in (
            alertmanager_resolution.candidates[0] if alertmanager_resolution.candidates else None,
            prometheus_resolution.candidates[0] if prometheus_resolution.candidates else None,
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
    cluster: Cluster,
    parameters: dict[str, str],
) -> DependencyBlocker | None:
    dataset = get_dataset(dataset_key)
    if dataset.source_kind == 'prometheus':
        return _prometheus_dependency_blocker(dataset_key=dataset_key, cluster=cluster)
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
    cluster = selected_cluster_from_request()
    normalized = canonical_parameters(dataset_key, parameters)
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
            dispatch_error = 'Analytics preparation could not be queued. Retry after worker capacity is available.'
    return MaterializedRequest(
        result,
        cluster,
        normalized,
        dispatched,
        dispatch_error,
        dependency_blocker,
    )
