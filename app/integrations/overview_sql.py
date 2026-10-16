"""Bounded SQL aggregate for global Integration Overview portfolio.

One aggregate row per registered capability instead of fetching every
provider ORM object just to count its persisted lifecycle/readiness state.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, case, func, or_, select

from app.extensions.db import db
from app.integrations.kernel.registry import registry
from app.models.alertmanager import AlertmanagerInstance
from app.models.integration import IntegrationInstance
from app.models.kubernetes import KubernetesConnection
from app.models.metrics_source import MetricsSource


def overview_portfolio_counts() -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    identity = IntegrationInstance
    kube = KubernetesConnection
    metrics = MetricsSource
    alerts = AlertmanagerInstance
    specialized = ('container_orchestrator', 'metrics_source', 'alert_source')
    modules = registry.all()
    if not modules:
        return {}, dict.fromkeys(
            (
                'total',
                'configured',
                'ready',
                'readiness_review',
                'validation_required',
                'not_configured',
                'attention',
                'blocked',
            ),
            0,
        )

    configured = case(
        (identity.integration_type == 'container_orchestrator', kube.id.is_not(None)),
        (
            identity.integration_type == 'metrics_source',
            and_(metrics.id.is_not(None), metrics.endpoint.is_not(None), metrics.endpoint != ''),
        ),
        (
            identity.integration_type == 'alert_source',
            and_(alerts.id.is_not(None), alerts.endpoint.is_not(None), alerts.endpoint != ''),
        ),
        else_=True,
    )
    # Provider runtime state is never a substitute for the canonical lifecycle.
    active = and_(identity.enabled.is_(True), identity.lifecycle_status == 'active')
    readiness = case(
        (identity.integration_type == 'container_orchestrator', kube.readiness_status),
        else_=identity.readiness_status,
    )
    state = func.coalesce(readiness, 'validation_required')
    ready = and_(configured, active, state == 'ready')
    eligible = and_(configured, active)
    disabled = and_(configured, ~active)
    blocked_states = ('blocked', 'unavailable', 'failed', 'incompatible')

    def count_when(predicate: Any):
        return func.coalesce(func.sum(case((predicate, 1), else_=0)), 0)

    statement = (
        select(
            identity.integration_type.label('integration_type'),
            func.count(identity.id).label('total'),
            count_when(configured).label('configured'),
            count_when(ready).label('ready'),
            count_when(and_(eligible, state == 'degraded')).label('degraded'),
            count_when(and_(eligible, state.in_(blocked_states))).label('blocked'),
            count_when(
                and_(
                    eligible,
                    ~state.in_(('ready', 'degraded', *blocked_states)),
                )
            ).label('validation_required'),
            count_when(disabled).label('disabled'),
        )
        .select_from(identity)
        .outerjoin(kube, kube.integration_instance_id == identity.id)
        .outerjoin(metrics, metrics.integration_instance_id == identity.id)
        .outerjoin(alerts, alerts.integration_instance_id == identity.id)
        .where(
            identity.integration_type.in_([module.integration_type for module in modules]),
            or_(
                ~identity.integration_type.in_(specialized),
                and_(identity.integration_type == 'container_orchestrator', kube.id.is_not(None)),
                and_(identity.integration_type == 'metrics_source', metrics.id.is_not(None)),
                and_(identity.integration_type == 'alert_source', alerts.id.is_not(None)),
            ),
        )
        .group_by(identity.integration_type)
    )
    counts: dict[str, dict[str, int]] = {}
    for record in db.session.execute(statement).mappings():
        category = str(record['integration_type'])
        values = {
            key: int(record[key] or 0)
            for key in (
                'total',
                'configured',
                'ready',
                'degraded',
                'blocked',
                'validation_required',
                'disabled',
            )
        }
        values['not_configured'] = values['total'] - values['configured']
        values['attention'] = values['total'] - values['ready']
        counts[category] = values
    totals = {
        name: sum(values[name] for values in counts.values())
        for name in ('total', 'configured', 'ready', 'blocked', 'not_configured')
    }
    totals['readiness_review'] = sum(values['configured'] - values['ready'] for values in counts.values())
    totals['validation_required'] = totals['readiness_review']
    totals['attention'] = totals['total'] - totals['ready']
    return counts, totals
