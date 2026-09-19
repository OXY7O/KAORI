from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import contains_eager

from app.common.pagination import paginate_sequence
from app.common.presentation import present_user_datetime
from app.integrations.coverage import bound_source_for_scope, bound_sources_for_scopes
from app.integrations.readiness import (
    OperationalPosture,
    resolve_binding_operational_status,
    resolve_cluster_coverage,
)
from app.kubernetes.cluster.constants import get_environment_label
from app.models import Cluster
from app.models.kubernetes import KubernetesConnection

READINESS_OPTIONS = [
    {'value': 'ready', 'label': 'Ready'},
    {'value': 'degraded', 'label': 'Degraded'},
    {'value': 'blocked', 'label': 'Blocked'},
    {'value': 'validation_required', 'label': 'Validation Required'},
]

COVERAGE_OPTIONS = [
    {'value': 'ready', 'label': 'Operational'},
    {'value': 'degraded', 'label': 'Partial Coverage'},
    {'value': 'not_configured', 'label': 'Setup Required'},
    {'value': 'blocked', 'label': 'Blocked'},
    {'value': 'validation_required', 'label': 'Validation Required'},
]


@dataclass(frozen=True, slots=True)
class KubernetesRegistryFilters:
    query: str = ''
    environment: str = ''
    readiness: str = ''
    coverage: str = ''
    page: int = 1
    per_page: int = 5


@dataclass(frozen=True, slots=True)
class KubernetesCoverageFilters:
    query: str = ''
    environment: str = ''
    status: str = ''
    page: int = 1
    per_page: int = 5


@dataclass(frozen=True, slots=True)
class KubernetesFrontPageFilters:
    registry: KubernetesRegistryFilters = field(default_factory=KubernetesRegistryFilters)
    coverage: KubernetesCoverageFilters = field(default_factory=KubernetesCoverageFilters)


def _provider_posture(source: Any | None, binding: Any | None) -> OperationalPosture:
    if source is None or binding is None:
        return {
            'status': 'not_configured',
            'label': 'Not Configured',
            'message': 'No eligible provider binding has been configured for this consumer.',
        }
    return resolve_binding_operational_status(
        source_readiness=getattr(source, 'readiness_status', None),
        binding_validation=getattr(binding, 'validation_status', None),
        source_enabled=bool(getattr(source, 'enabled', True)),
        binding_enabled=bool(getattr(binding, 'enabled', True)),
    )


def _inventory_coverage(readiness: str) -> OperationalPosture:
    labels = {
        'ready': 'Ready',
        'degraded': 'Degraded',
        'blocked': 'Blocked',
    }
    if readiness in labels:
        return {
            'status': readiness,
            'label': labels[readiness],
            'message': 'Kubernetes Inventory follows the direct Kubernetes API readiness gate.',
        }
    return {
        'status': 'validation_required',
        'label': 'Validation Required',
        'message': 'Run Kubernetes Core Validation before Inventory is treated as operationally ready.',
    }


def _coverage_summary(
    *,
    readiness: str,
    coverage_items: tuple[OperationalPosture, OperationalPosture, OperationalPosture],
) -> dict[str, str]:
    ready_count = sum(1 for item in coverage_items if item['status'] == 'ready')
    if readiness in {'blocked', 'degraded'}:
        return {'status': readiness, 'label': readiness.title()}
    if readiness != 'ready':
        return {'status': 'validation_required', 'label': 'Validation Required'}
    if ready_count == len(coverage_items):
        return {'status': 'ready', 'label': 'Operational'}
    if any(item['status'] == 'not_configured' for item in coverage_items):
        return {'status': 'not_configured', 'label': 'Setup Required'}
    if ready_count:
        return {'status': 'degraded', 'label': f'{ready_count} of {len(coverage_items)} Ready'}
    return {'status': 'validation_required', 'label': 'Validation Required'}


def _build_registry_row(
    connection: KubernetesConnection,
    *,
    bound_sources: dict[tuple[str, str], tuple[Any | None, Any | None]] | None = None,
) -> dict[str, Any]:
    cluster = connection.cluster
    if bound_sources is None:
        metrics_source, metrics_binding = bound_source_for_scope(
            'metrics_source', scope_type='kubernetes_cluster', scope_key=cluster.id
        )
        alertmanager, alertmanager_binding = bound_source_for_scope(
            'alert_source', scope_type='kubernetes_cluster', scope_key=cluster.id
        )
    else:
        metrics_source, metrics_binding = bound_sources.get(('metrics_source', str(cluster.id)), (None, None))
        alertmanager, alertmanager_binding = bound_sources.get(('alert_source', str(cluster.id)), (None, None))

    metrics_operational = _provider_posture(metrics_source, metrics_binding)
    alerts_operational = _provider_posture(alertmanager, alertmanager_binding)
    metrics_coverage = resolve_cluster_coverage(
        kubernetes_readiness=connection.readiness_status,
        source=metrics_source,
        binding=metrics_binding,
    )
    alerts_coverage = resolve_cluster_coverage(
        kubernetes_readiness=connection.readiness_status,
        source=alertmanager,
        binding=alertmanager_binding,
    )
    readiness = connection.readiness_status or 'validation_required'
    inventory_coverage = _inventory_coverage(readiness)
    coverage_items = (inventory_coverage, metrics_coverage, alerts_coverage)
    coverage_summary = _coverage_summary(readiness=readiness, coverage_items=coverage_items)

    source_bindings = tuple(
        binding
        for binding in (metrics_binding, alertmanager_binding)
        if binding is not None and bool(getattr(binding, 'enabled', True))
    )
    source_postures = (metrics_operational, alerts_operational)

    return {
        'connection_id': connection.id,
        'integration_instance_id': connection.integration_instance_id,
        'cluster_id': cluster.id,
        'cluster_name': cluster.name,
        'environment': get_environment_label(cluster.environment),
        'server': connection.server or 'Not discovered',
        'readiness': readiness,
        'inventory_coverage': inventory_coverage,
        'metrics_coverage': metrics_coverage,
        'alerts_coverage': alerts_coverage,
        'coverage_summary': coverage_summary,
        'coverage_ready_count': sum(1 for item in coverage_items if item['status'] == 'ready'),
        'compatibility_profile': connection.compatibility_profile,
        'version': connection.detected_version,
        'source_binding_count': len(source_bindings),
        'source_operational_count': sum(1 for item in source_postures if item['status'] == 'ready'),
        'metrics_source_id': metrics_source.id if metrics_source else None,
        'metrics_source_name': metrics_source.name if metrics_source else None,
        'metrics_source_status': getattr(metrics_source, 'readiness_status', None),
        'metrics_binding_status': metrics_binding.validation_status if metrics_binding else None,
        'metrics_source_operational': metrics_operational,
        'alertmanager_instance_id': alertmanager.id if alertmanager else None,
        'alertmanager_name': alertmanager.name if alertmanager else None,
        'alertmanager_source_status': getattr(alertmanager, 'readiness_status', None),
        'alertmanager_binding_status': alertmanager_binding.validation_status if alertmanager_binding else None,
        'alertmanager_operational': alerts_operational,
        'last_validated_at': present_user_datetime(connection.last_validated_at, empty='Not validated'),
    }


def build_kubernetes_registry_row(cluster_id: str) -> dict[str, Any] | None:
    connection = KubernetesConnection.query.filter_by(cluster_id=cluster_id).first()
    if connection is None:
        return None
    return _build_registry_row(connection)


def _load_rows() -> list[dict[str, Any]]:
    connections = (
        KubernetesConnection.query.join(Cluster)
        .options(contains_eager(KubernetesConnection.cluster))
        .order_by(Cluster.created_at.asc(), Cluster.id.asc())
        .all()
    )
    bound_sources = bound_sources_for_scopes(
        ('metrics_source', 'alert_source'),
        scope_type='kubernetes_cluster',
        scope_keys=[str(connection.cluster_id) for connection in connections],
    )
    return [_build_registry_row(connection, bound_sources=bound_sources) for connection in connections]


def _search_blob(row: dict[str, Any], fields: tuple[str, ...]) -> str:
    return ' '.join(str(row.get(field) or '') for field in fields).lower()


def _filter_registry_rows(
    rows: list[dict[str, Any]], filters: KubernetesRegistryFilters
) -> tuple[list[dict[str, Any]], str]:
    normalized_query = filters.query.strip().lower()
    filtered = list(rows)
    if normalized_query:
        fields = ('cluster_name', 'environment', 'server', 'version', 'compatibility_profile')
        filtered = [row for row in filtered if normalized_query in _search_blob(row, fields)]
    if filters.environment:
        filtered = [row for row in filtered if row.get('environment') == filters.environment]
    if filters.readiness:
        filtered = [row for row in filtered if row.get('readiness') == filters.readiness]
    if filters.coverage:
        filtered = [row for row in filtered if (row.get('coverage_summary') or {}).get('status') == filters.coverage]
    return filtered, normalized_query


def _filter_coverage_rows(
    rows: list[dict[str, Any]], filters: KubernetesCoverageFilters
) -> tuple[list[dict[str, Any]], str]:
    normalized_query = filters.query.strip().lower()
    filtered = list(rows)
    if normalized_query:
        fields = ('cluster_name', 'environment', 'server', 'metrics_source_name', 'alertmanager_name')
        filtered = [
            row
            for row in filtered
            if normalized_query in _search_blob(row, fields)
            or normalized_query in str((row.get('coverage_summary') or {}).get('label') or '').lower()
        ]
    if filters.environment:
        filtered = [row for row in filtered if row.get('environment') == filters.environment]
    if filters.status:
        filtered = [row for row in filtered if (row.get('coverage_summary') or {}).get('status') == filters.status]
    return filtered, normalized_query


def _stats(rows: list[dict[str, Any]]) -> dict[str, int]:
    total = len(rows)
    ready = sum(1 for row in rows if row['readiness'] == 'ready')
    return {
        'total': total,
        'ready': ready,
        'attention': total - ready,
        'bindings': sum(row['source_binding_count'] for row in rows),
        'fully_operational': sum(1 for row in rows if row['coverage_summary']['status'] == 'ready'),
        'metrics_source_configured': sum(1 for row in rows if row['metrics_source_id']),
        'metrics_source_ready': sum(1 for row in rows if row['metrics_source_status'] == 'ready'),
        'metrics_binding_ready': sum(1 for row in rows if row['metrics_binding_status'] == 'ready'),
        'metrics_source_operational': sum(1 for row in rows if row['metrics_source_operational']['status'] == 'ready'),
        'alertmanager_configured': sum(1 for row in rows if row['alertmanager_instance_id']),
        'alertmanager_source_ready': sum(1 for row in rows if row['alertmanager_source_status'] == 'ready'),
        'alertmanager_binding_ready': sum(1 for row in rows if row['alertmanager_binding_status'] == 'ready'),
        'alertmanager_operational': sum(1 for row in rows if row['alertmanager_operational']['status'] == 'ready'),
    }


def build_kubernetes_page(filters: KubernetesFrontPageFilters | None = None) -> dict[str, Any]:
    resolved = filters or KubernetesFrontPageFilters()
    rows = _load_rows()
    registry_rows, registry_query = _filter_registry_rows(rows, resolved.registry)
    coverage_rows, coverage_query = _filter_coverage_rows(rows, resolved.coverage)
    page_rows, pagination = paginate_sequence(
        registry_rows, page=resolved.registry.page, per_page=resolved.registry.per_page
    )
    coverage_page_rows, coverage_pagination = paginate_sequence(
        coverage_rows, page=resolved.coverage.page, per_page=resolved.coverage.per_page
    )
    environments = sorted({row['environment'] for row in rows if row.get('environment')})

    return {
        'rows': page_rows,
        'pagination': pagination,
        'coverage_rows': coverage_page_rows,
        'coverage_pagination': coverage_pagination,
        'selected_query': resolved.registry.query,
        'selected_environment': resolved.registry.environment,
        'selected_readiness': resolved.registry.readiness,
        'selected_coverage': resolved.registry.coverage,
        'selected_coverage_query': resolved.coverage.query,
        'selected_coverage_environment': resolved.coverage.environment,
        'selected_coverage_status': resolved.coverage.status,
        'registry_has_active_filters': bool(
            registry_query or resolved.registry.environment or resolved.registry.readiness or resolved.registry.coverage
        ),
        'coverage_has_active_filters': bool(
            coverage_query or resolved.coverage.environment or resolved.coverage.status
        ),
        'environment_options': environments,
        'coverage_environment_options': environments,
        'readiness_options': READINESS_OPTIONS,
        'coverage_options': COVERAGE_OPTIONS,
        'coverage_status_options': COVERAGE_OPTIONS,
        'stats': _stats(rows),
    }
