"""Global Integration Overview: SQL fleet summaries, page-bounded runtime detail."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.extensions.db import db
from app.integrations.kernel.registry import get_integration, registry
from app.integrations.overview_runtime_sql import (
    runtime_filter,
    runtime_fleet,
    runtime_page,
    runtime_stats,
)
from app.integrations.overview_sql import overview_portfolio_counts
from app.integrations.service import (
    _alertmanager_runtime_row,
    _catalog,
    _coverage,
    _coverage_stats,
    _kubernetes_runtime_row,
    _metrics_source_runtime_row,
    _runtime_scope_label,
)
from app.models import AlertmanagerInstance, MetricsSource
from app.models.integration import IntegrationInstance
from app.models.kubernetes import KubernetesConnection
from app.models.runtime import IntegrationRuntimeObservation


def _visible_runtime_rows(specs: list[Any]) -> list[dict[str, Any]]:
    """Hydrate only the visible provider records and their latest observations."""
    if not specs:
        return []
    observation_ids = {
        int(item['observation_id'])
        for item in specs if item['observation_id'] is not None
    }
    observations = (
        db.session.scalars(
            select(IntegrationRuntimeObservation).where(
                IntegrationRuntimeObservation.id.in_(observation_ids)
            )
        ).all() if observation_ids else []
    )
    latest = {(row.integration_type, row.instance_id): row for row in observations}
    by_type: dict[str, list[int]] = defaultdict(list)
    for item in specs:
        by_type[str(item['integration_type'])].append(int(item['provider_record_id']))

    core_models = {
        'container_orchestrator': (KubernetesConnection, _kubernetes_runtime_row),
        'metrics_source': (MetricsSource, _metrics_source_runtime_row),
        'alert_source': (AlertmanagerInstance, _alertmanager_runtime_row),
    }
    core_rows: dict[tuple[str, int], dict[str, Any]] = {}
    for integration_type, (model, builder) in core_models.items():
        ids = by_type.get(integration_type)
        if not ids:
            continue
        options = [selectinload(model.integration_instance)]
        if integration_type == 'container_orchestrator':
            options.append(selectinload(KubernetesConnection.cluster))
        else:
            options = [
                selectinload(model.integration_instance).selectinload(
                    IntegrationInstance.bindings
                )
            ]
        records = db.session.scalars(
            select(model).where(model.id.in_(ids)).options(*options)
        ).all()
        for record in records:
            core_rows[(integration_type, record.id)] = builder(record, latest)

    rows: list[dict[str, Any]] = []
    for item in specs:
        typ = str(item['integration_type'])
        record_id = int(item['provider_record_id'])
        if typ in core_models:
            row = core_rows.get((typ, record_id))
            if row is not None:
                rows.append(row)
            continue
        # Provider-owned runtime builders already support a *canonical* ID.
        # Never pass a provider-record ID into the canonical registry resolver.
        module = get_integration(typ)
        projected = module.build_runtime_overview_rows(latest, int(item['canonical_id']))
        if projected:
            rows.append(projected[0])
    return rows


def build_integrations_overview(
    *,
    tab: str = 'catalog',
    integration_type: str = '',
    health: str = '',
    readiness: str = '',
    page: int = 1,
    per_page: int = 5,
) -> dict[str, Any]:
    """Provider-neutral committed overview, without live provider requests.

    Global counters and filtered runtime scope are SQL aggregates; ORM
    records/bindings are hydrated only for selected Runtime page rows.
    """
    active_tab = tab if tab in {'catalog', 'runtime', 'coverage'} else 'catalog'
    modules = registry.all()
    provider_counts, stats = overview_portfolio_counts()
    context: dict[str, Any] = {
        'stats': stats,
        'available_provider_count': len(modules),
        'available_domain_count': len({module.domain_key for module in modules}),
        'active_tab': active_tab,
    }
    if active_tab == 'catalog':
        context['catalog'] = _catalog(
            kubernetes_connections=[],
            metrics_sources=[],
            alertmanager_instances=[],
            extension_instances=[],
            provider_counts_override=provider_counts,
        )
        return context
    if active_tab == 'coverage':
        coverage = _coverage(
            kubernetes_connections=[],
            metrics_sources=[],
            alertmanager_instances=[],
            extension_instances=[],
            provider_counts_override=provider_counts,
        )
        context['coverage'] = coverage
        context['coverage_stats'] = _coverage_stats(coverage)
        return context

    fleet = runtime_fleet()
    global_stats = runtime_stats(fleet)
    selected = (
        runtime_filter(
            fleet, integration_type=integration_type, health=health,
            readiness=readiness,
        )
        if fleet is not None else None
    )
    filtered_stats = runtime_stats(selected)
    specs, pagination = runtime_page(selected, page=page, per_page=per_page)
    context.update({
        'runtime_rows': _visible_runtime_rows(specs),
        'runtime_stats': filtered_stats,
        'runtime_global_stats': global_stats,
        'runtime_scope_label': _runtime_scope_label(
            integration_type=integration_type, health=health, readiness=readiness,
        ),
        'runtime_pagination': pagination,
        'runtime_has_targets': bool(global_stats['total']),
        'selected_integration_type': integration_type,
        'selected_health': health,
        'selected_readiness': readiness,
        'integration_type_options': [
            {'value': module.integration_type, 'label': module.runtime_label or module.label}
            for module in modules
        ],
        'health_options': [
            {'value': 'healthy', 'label': 'Healthy'},
            {'value': 'degraded', 'label': 'Degraded'},
            {'value': 'unhealthy', 'label': 'Unhealthy'},
            {'value': 'not_observed', 'label': 'Not Observed'},
        ],
        'runtime_readiness_options': [
            {'value': 'ready', 'label': 'Ready'},
            {'value': 'degraded', 'label': 'Degraded'},
            {'value': 'blocked', 'label': 'Blocked'},
            {'value': 'validation_required', 'label': 'Validation Required'},
        ],
    })
    return context
