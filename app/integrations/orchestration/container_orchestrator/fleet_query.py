"""SQL-first Kubernetes Connection Registry and Coverage projections.

The per-page ORM hydration is intentionally outside this module. All fleet
counts, source posture and filter decisions are computed from committed SQL
state before selecting visible Kubernetes connections.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import String, and_, case, cast, func, literal, or_, select
from sqlalchemy.orm import aliased

from app.common.pagination import build_pagination_window, pagination_payload
from app.extensions.db import db
from app.kubernetes.cluster.constants import ENVIRONMENTS
from app.models.alertmanager import AlertmanagerInstance
from app.models.cluster import Cluster
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.kubernetes import KubernetesConnection
from app.models.metrics_source import MetricsSource


def _preferred_binding_id(integration_type: str):
    candidate = aliased(IntegrationBinding)
    identity = aliased(IntegrationInstance)
    role_rank = case(
        (candidate.binding_role == 'primary', 0),
        (candidate.binding_role == 'secondary', 1),
        (candidate.binding_role == 'fallback', 2),
        else_=9,
    )
    return (
        select(candidate.id)
        .join(identity, identity.id == candidate.integration_instance_id)
        .where(
            candidate.asset_type == 'kubernetes_cluster',
            candidate.asset_key == Cluster.id,
            candidate.enabled.is_(True),
            identity.integration_type == integration_type,
        )
        .order_by(role_rank, candidate.priority, candidate.id)
        .limit(1)
        .correlate(Cluster)
        .scalar_subquery()
    )


def _source_status(binding: Any, identity: Any, provider: Any):
    """Match the existing source-first readiness composition without live calls."""
    return case(
        (binding.id.is_(None), 'not_configured'),
        (identity.id.is_(None), 'not_configured'),
        (provider.id.is_(None), 'not_configured'),
        (identity.enabled.is_(False), 'not_configured'),
        (func.coalesce(identity.lifecycle_status, 'inactive') != 'active', 'not_configured'),
        (identity.readiness_status == 'blocked', 'blocked'),
        (identity.readiness_status == 'degraded', 'degraded'),
        (func.coalesce(identity.readiness_status, 'validation_required') != 'ready', 'validation_required'),
        (binding.validation_status == 'blocked', 'blocked'),
        (binding.validation_status == 'degraded', 'degraded'),
        (func.coalesce(binding.validation_status, 'validation_required') != 'ready', 'validation_required'),
        else_='ready',
    )


def fleet_statement():
    """One row per registered KubernetesConnection, including inactive entries."""
    canonical = aliased(IntegrationInstance)
    mb, ab = aliased(IntegrationBinding), aliased(IntegrationBinding)
    mi, ai = aliased(IntegrationInstance), aliased(IntegrationInstance)
    mp, ap = aliased(MetricsSource), aliased(AlertmanagerInstance)

    readiness = case(
        (canonical.id.is_(None), 'blocked'),
        (canonical.enabled.is_(False), 'blocked'),
        (func.coalesce(canonical.lifecycle_status, 'inactive') != 'active', 'blocked'),
        else_=func.coalesce(KubernetesConnection.readiness_status, 'validation_required'),
    )
    metrics_source = _source_status(mb, mi, mp)
    alert_source = _source_status(ab, ai, ap)
    # A non-Ready Kubernetes API blocks dependent consumers before their own
    # binding/transport evidence is evaluated.
    metrics_coverage = case(
        (readiness == 'blocked', 'blocked'),
        (readiness == 'degraded', 'degraded'),
        (readiness != 'ready', 'validation_required'),
        else_=metrics_source,
    )
    alert_coverage = case(
        (readiness == 'blocked', 'blocked'),
        (readiness == 'degraded', 'degraded'),
        (readiness != 'ready', 'validation_required'),
        else_=alert_source,
    )
    ready_count = (
        case((readiness == 'ready', 1), else_=0)
        + case((metrics_coverage == 'ready', 1), else_=0)
        + case((alert_coverage == 'ready', 1), else_=0)
    )
    coverage = case(
        (readiness == 'blocked', 'blocked'),
        (readiness == 'degraded', 'degraded'),
        (readiness != 'ready', 'validation_required'),
        (and_(metrics_coverage == 'ready', alert_coverage == 'ready'), 'ready'),
        (or_(metrics_coverage == 'not_configured', alert_coverage == 'not_configured'), 'not_configured'),
        else_='degraded',
    )
    label = case(
        (readiness == 'blocked', 'Blocked'),
        (readiness == 'degraded', 'Degraded'),
        (readiness != 'ready', 'Validation Required'),
        (coverage == 'ready', 'Operational'),
        (coverage == 'not_configured', 'Setup Required'),
        else_=cast(ready_count, String) + literal(' of 3 Ready'),
    )
    environment_label = case(
        *((Cluster.environment == key, label) for key, label in ENVIRONMENTS),
        else_=Cluster.environment,
    )
    return (
        select(
            KubernetesConnection.id.label('connection_id'),
            Cluster.id.label('cluster_id'),
            Cluster.name.label('cluster_name'),
            Cluster.created_at.label('created_at'),
            environment_label.label('environment'),
            KubernetesConnection.server.label('server'),
            KubernetesConnection.detected_version.label('version'),
            KubernetesConnection.compatibility_profile.label('compatibility_profile'),
            readiness.label('readiness'),
            coverage.label('coverage_status'),
            label.label('coverage_label'),
            mb.id.label('metrics_binding_id'),
            ab.id.label('alerts_binding_id'),
            mp.id.label('metrics_id'),
            ap.id.label('alertmanager_id'),
            case((mp.id.is_not(None), mi.name), else_=None).label('metrics_name'),
            case((ap.id.is_not(None), ai.name), else_=None).label('alerts_name'),
            mi.readiness_status.label('metrics_readiness'),
            ai.readiness_status.label('alerts_readiness'),
            mi.enabled.label('metrics_source_enabled'),
            ai.enabled.label('alerts_source_enabled'),
            mi.lifecycle_status.label('metrics_source_lifecycle'),
            ai.lifecycle_status.label('alerts_source_lifecycle'),
            mb.validation_status.label('metrics_binding_validation'),
            ab.validation_status.label('alerts_binding_validation'),
            metrics_source.label('metrics_source_status'),
            alert_source.label('alert_source_status'),
            metrics_coverage.label('metrics_coverage_status'),
            alert_coverage.label('alerts_coverage_status'),
        )
        .select_from(KubernetesConnection)
        .join(Cluster, Cluster.id == KubernetesConnection.cluster_id)
        .outerjoin(canonical, canonical.id == KubernetesConnection.integration_instance_id)
        .outerjoin(mb, mb.id == _preferred_binding_id('metrics_source'))
        .outerjoin(mi, mi.id == mb.integration_instance_id)
        .outerjoin(mp, mp.integration_instance_id == mi.id)
        .outerjoin(ab, ab.id == _preferred_binding_id('alert_source'))
        .outerjoin(ai, ai.id == ab.integration_instance_id)
        .outerjoin(ap, ap.integration_instance_id == ai.id)
        .subquery('kubernetes_fleet')
    )


def fleet_stats(fleet: Any) -> dict[str, int]:
    def present(expression: Any):
        return func.coalesce(func.sum(case((expression, 1), else_=0)), 0)

    result = db.session.execute(
        select(
            func.count().label('total'),
            present(fleet.c.readiness == 'ready').label('ready'),
            present(fleet.c.coverage_status == 'ready').label('fully_operational'),
            func.coalesce(func.sum(
                case((fleet.c.metrics_binding_id.is_not(None), 1), else_=0)
                + case((fleet.c.alerts_binding_id.is_not(None), 1), else_=0)
            ), 0).label('bindings'),
            present(fleet.c.metrics_id.is_not(None)).label('metrics_source_configured'),
            present(and_(
                fleet.c.metrics_id.is_not(None),
                fleet.c.metrics_readiness == 'ready',
                fleet.c.metrics_source_enabled.is_(True),
                fleet.c.metrics_source_lifecycle == 'active',
            )).label('metrics_source_ready'),
            present(fleet.c.metrics_binding_validation == 'ready').label('metrics_binding_ready'),
            present(fleet.c.metrics_source_status == 'ready').label('metrics_source_operational'),
            present(fleet.c.alertmanager_id.is_not(None)).label('alertmanager_configured'),
            present(and_(
                fleet.c.alertmanager_id.is_not(None),
                fleet.c.alerts_readiness == 'ready',
                fleet.c.alerts_source_enabled.is_(True),
                fleet.c.alerts_source_lifecycle == 'active',
            )).label('alertmanager_source_ready'),
            present(fleet.c.alerts_binding_validation == 'ready').label('alertmanager_binding_ready'),
            present(fleet.c.alert_source_status == 'ready').label('alertmanager_operational'),
        ).select_from(fleet)
    ).mappings().one()
    stats = {name: int(value or 0) for name, value in result.items()}
    stats['attention'] = stats['total'] - stats['ready']
    return stats


def environment_options(fleet: Any) -> list[str]:
    return sorted({
        label for label in db.session.scalars(
            select(fleet.c.environment).distinct()
        ).all() if label
    })


def page_connection_ids(
    fleet: Any,
    *,
    filters: Any,
    coverage: bool,
) -> tuple[list[int], dict[str, Any]]:
    """Filter and paginate scalar IDs in SQL, before ORM/source hydration."""
    statement = select(fleet.c.connection_id)
    search = filters.query.strip().lower()
    if search:
        term = f'%{search}%'
        searchable = [
            fleet.c.cluster_name, fleet.c.environment,
            func.coalesce(fleet.c.server, 'Not discovered'),
        ]
        if coverage:
            searchable.extend((
                fleet.c.metrics_name,
                fleet.c.alerts_name,
                fleet.c.coverage_label,
            ))
        else:
            searchable.extend((fleet.c.version, fleet.c.compatibility_profile))
        statement = statement.where(or_(*(
            func.lower(func.coalesce(field, '')).like(term)
            for field in searchable
        )))
    if filters.environment:
        statement = statement.where(fleet.c.environment == filters.environment)
    if coverage:
        if filters.status:
            statement = statement.where(fleet.c.coverage_status == filters.status)
    else:
        if filters.readiness:
            statement = statement.where(fleet.c.readiness == filters.readiness)
        if filters.coverage:
            statement = statement.where(fleet.c.coverage_status == filters.coverage)
    count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    count = int(db.session.scalar(count_statement) or 0)
    window = build_pagination_window(
        total_items=count, page=filters.page, per_page=filters.per_page,
    )
    ids = db.session.scalars(
        statement.order_by(fleet.c.created_at, fleet.c.cluster_id)
        .offset(window.offset).limit(window.per_page)
    ).all()
    return list(ids), pagination_payload(window)
