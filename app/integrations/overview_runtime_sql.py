"""SQL-first bounded Runtime Overview candidate and committed observation index.

Provider implementations expose their registered ORM record_model; only the
selected page is hydrated through the existing provider runtime row builders.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import String, and_, case, cast, func, literal, select, union_all
from sqlalchemy.dialects.postgresql import JSONB, JSONPATH
from sqlalchemy.orm import aliased

from app.common.pagination import build_pagination_window, pagination_payload
from app.extensions.db import db
from app.integrations.kernel.registry import registry
from app.integrations.provider_matrix import provider_kind
from app.models.integration import IntegrationInstance
from app.models.runtime import IntegrationRuntimeObservation


def runtime_fleet():
    projections = []
    for module in registry.all():
        for implementation in registry.implementations_for_type(module.integration_type):
            model = implementation.record_model
            if model is None or (
                implementation.runtime_overview_builder is None
                and module.integration_type not in {
                    'container_orchestrator', 'metrics_source', 'alert_source'
                }
            ):
                continue
            canonical = IntegrationInstance
            readiness = (
                model.readiness_status if module.integration_type == 'container_orchestrator'
                else canonical.readiness_status
            )
            ready = case(
                (
                    and_(canonical.enabled.is_(True), canonical.lifecycle_status == 'active'),
                    func.coalesce(readiness, 'validation_required'),
                ),
                else_='blocked',
            )
            if module.integration_type == 'container_orchestrator':
                attention = case((ready == 'ready', 0), else_=1)
            elif module.integration_type == 'metrics_source':
                # Statuses are persisted in the provider's canonical capability
                # assessment, not inferred from connection readiness.
                invalid_assessment = func.jsonb_path_exists(
                    cast(model.capabilities, JSONB),
                    cast(literal('$.assessments[*] ? (@.status != "available")'), JSONPATH),
                )
                attention = case((invalid_assessment.is_(True), 1), else_=0)
            else:
                # All other current providers use a collection of validated
                # capability names/profiles. Empty persisted evidence is attention.
                missing = (
                    model.capabilities.is_(None)
                    | cast(model.capabilities, String).in_(('[]', '{}', 'null'))
                )
                attention = case((missing, 1), else_=0)
            provider = provider_kind(module.integration_type, implementation.provider_key)
            projections.append(
                select(
                    literal(module.integration_type).label('integration_type'),
                    literal(implementation.provider_key).label('provider_key'),
                    literal(provider.label).label('provider_label'),
                    canonical.id.label('canonical_id'),
                    model.id.label('provider_record_id'),
                    canonical.name.label('instance_name'),
                    ready.label('readiness'),
                    attention.label('capability_attention'),
                )
                .select_from(model)
                .join(canonical, canonical.id == model.integration_instance_id)
                .where(
                    canonical.integration_type == module.integration_type,
                    canonical.provider_key == implementation.provider_key,
                )
            )
    if not projections:
        return None
    candidates = union_all(*projections).subquery('overview_runtime_candidates')
    observation = IntegrationRuntimeObservation
    lookup = aliased(IntegrationRuntimeObservation)
    latest_id = (
        select(lookup.id)
        .where(
            lookup.integration_type == candidates.c.integration_type,
            lookup.instance_id == cast(candidates.c.provider_record_id, String),
        )
        .order_by(lookup.observed_at.desc(), lookup.id.desc())
        .limit(1)
        .correlate(candidates)
        .scalar_subquery()
    )
    return (
        select(
            *candidates.c,
            observation.id.label('observation_id'),
            func.coalesce(observation.health_status, 'not_observed').label('health_status'),
        )
        .select_from(candidates)
        .outerjoin(observation, observation.id == latest_id)
        .subquery('overview_runtime_fleet')
    )


def runtime_filter(fleet: Any, *, integration_type: str, health: str, readiness: str):
    statement = select(fleet)
    if integration_type:
        statement = statement.where(fleet.c.integration_type == integration_type)
    if health:
        statement = statement.where(fleet.c.health_status == health)
    if readiness:
        statement = statement.where(fleet.c.readiness == readiness)
    return statement.subquery('filtered_runtime_fleet')


def runtime_stats(fleet: Any | None) -> dict[str, int]:
    keys = ('total', 'healthy', 'degraded', 'unhealthy', 'not_observed', 'capability_attention')
    if fleet is None:
        return dict.fromkeys(keys, 0)
    def count_when(predicate: Any):
        return func.coalesce(func.sum(case((predicate, 1), else_=0)), 0)
    row = db.session.execute(
        select(
            func.count().label('total'),
            count_when(fleet.c.health_status == 'healthy').label('healthy'),
            count_when(fleet.c.health_status == 'degraded').label('degraded'),
            count_when(fleet.c.health_status == 'unhealthy').label('unhealthy'),
            count_when(fleet.c.health_status == 'not_observed').label('not_observed'),
            count_when(fleet.c.capability_attention > 0).label('capability_attention'),
        ).select_from(fleet)
    ).mappings().one()
    return {key: int(row[key] or 0) for key in keys}


def runtime_page(
    fleet: Any | None, *, page: int, per_page: int
) -> tuple[list[Any], dict[str, Any]]:
    if fleet is None:
        window = build_pagination_window(total_items=0, page=page, per_page=per_page)
        return [], pagination_payload(window)
    count = int(db.session.scalar(select(func.count()).select_from(fleet)) or 0)
    window = build_pagination_window(total_items=count, page=page, per_page=per_page)
    health_rank = case(
        (fleet.c.health_status == 'unhealthy', 0),
        (fleet.c.health_status == 'degraded', 1),
        (fleet.c.health_status == 'healthy', 3),
        else_=2,
    )
    rows = db.session.execute(
        select(fleet)
        .order_by(
            health_rank,
            fleet.c.provider_label,
            func.lower(fleet.c.instance_name),
            fleet.c.integration_type,
            fleet.c.canonical_id,
        )
        .offset(window.offset).limit(window.per_page)
    ).mappings().all()
    return rows, pagination_payload(window)
