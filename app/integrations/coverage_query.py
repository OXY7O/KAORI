"""SQL-first fleet Coverage queries; source-specific projection stays in coverage.py."""

from __future__ import annotations

from typing import Any

from sqlalchemy import String, and_, case, cast, func, literal, or_, select, union_all
from sqlalchemy.orm import aliased

from app.common.pagination import build_pagination_window, pagination_payload
from app.extensions.db import db
from app.integrations.consumer_assets import registered_consumer_asset_definitions
from app.integrations.kernel.registry import registry
from app.kubernetes.cluster.constants import ENVIRONMENTS, get_environment_label
from app.models.integration import IntegrationBinding, IntegrationInstance


def _coverage_statement(integration_type: str):
    definitions = registered_consumer_asset_definitions()
    assets = []
    for position, definition in enumerate(definitions):
        model = definition.model
        stmt = select(
            literal(position).label('position'),
            literal(definition.asset_type).label('asset_type'),
            cast(model.id, String).label('asset_key'),
            model.name.label('asset_name'),
            func.coalesce(model.environment, '').label('environment'),
            literal(f'{definition.label.lower()} {definition.asset_type.replace("_", " ")}').label('hint'),
        )
        if definition.integration_type and model is IntegrationInstance:
            stmt = stmt.where(IntegrationInstance.integration_type == definition.integration_type)
        assets.append(stmt)
    if not assets:
        raise ValueError('Registered consumer asset definitions are required for Coverage.')
    scopes = union_all(*assets).subquery('coverage_scopes')

    rank = case(
        (IntegrationBinding.binding_role == 'primary', 0),
        (IntegrationBinding.binding_role == 'secondary', 1),
        (IntegrationBinding.binding_role == 'fallback', 2),
        else_=9,
    )
    bindings = (
        select(
            IntegrationBinding.id.label('binding_id'),
            IntegrationBinding.asset_type,
            IntegrationBinding.asset_key,
            IntegrationBinding.integration_instance_id,
            IntegrationBinding.validation_status,
            IntegrationBinding.selector_json,
            func.count().over(
                partition_by=IntegrationBinding.integration_instance_id
            ).label('sharing_count'),
            func.row_number().over(
                partition_by=(IntegrationBinding.asset_type, IntegrationBinding.asset_key),
                order_by=(rank, IntegrationBinding.priority, IntegrationBinding.id),
            ).label('position'),
        )
        .join(IntegrationInstance, IntegrationInstance.id == IntegrationBinding.integration_instance_id)
        .where(
            IntegrationInstance.integration_type == integration_type,
            IntegrationBinding.enabled.is_(True),
        )
        .subquery('coverage_bindings')
    )
    source = aliased(IntegrationInstance)
    winner = bindings
    provider_models = tuple(dict.fromkeys(
        implementation.record_model
        for implementation in registry.implementations_for_type(integration_type)
        if implementation.record_model is not None
    ))
    provider_checks = [
        select(model.id).where(model.integration_instance_id == source.id).exists()
        for model in provider_models
    ]
    # An orphaned canonical source may retain old Ready state; never count it.
    provider_record_exists = or_(*provider_checks) if provider_checks else literal(True)
    missing_selector = or_(
        winner.c.selector_json.is_(None),
        winner.c.selector_json['matchers'][0]['label'].as_string().is_(None),
        winner.c.selector_json['matchers'][0]['value'].as_string().is_(None),
        winner.c.selector_json['matchers'][0]['label'].as_string() == '',
        winner.c.selector_json['matchers'][0]['value'].as_string() == '',
    )
    state = case(
        (winner.c.binding_id.is_(None), 'uncovered'),
        (source.id.is_(None), 'blocked'),
        (~provider_record_exists, 'blocked'),
        (source.enabled.is_(False), 'blocked'),
        (source.lifecycle_status != 'active', 'blocked'),
        (and_(winner.c.sharing_count > 1, missing_selector), 'blocked'),
        (winner.c.validation_status == 'blocked', 'blocked'),
        (winner.c.validation_status == 'degraded', 'degraded'),
        (func.coalesce(winner.c.validation_status, 'validation_required') != 'ready', 'validation_required'),
        (source.readiness_status == 'ready', 'ready'),
        (source.readiness_status == 'degraded', 'degraded'),
        (source.readiness_status == 'blocked', 'blocked'),
        else_='validation_required',
    )
    return (
        select(
            scopes.c.position,
            scopes.c.asset_type,
            scopes.c.asset_key,
            scopes.c.asset_name,
            scopes.c.environment,
            scopes.c.hint,
            winner.c.binding_id,
            winner.c.integration_instance_id,
            source.name.label('source_name'),
            state.label('coverage_status'),
        )
        .select_from(
            scopes.outerjoin(
                winner,
                and_(
                    winner.c.asset_type == scopes.c.asset_type,
                    winner.c.asset_key == scopes.c.asset_key,
                    winner.c.position == 1,
                ),
            ).outerjoin(source, source.id == winner.c.integration_instance_id)
        )
        .subquery('coverage_scope_status')
    )


def paged_coverage_scopes(
    integration_type: str, *, page: int, per_page: int,
    query: str = '', environment: str = '', status: str = '',
) -> dict[str, Any]:
    """Aggregate fleet posture in SQL and hydrate only the filtered visible asset page."""
    scope = _coverage_statement(integration_type)
    session = db.session
    total, ready, attention, uncovered = session.execute(
        select(
            func.count(),
            func.sum(case((scope.c.coverage_status == 'ready', 1), else_=0)),
            func.sum(case((scope.c.coverage_status.in_(
                ('degraded', 'validation_required', 'blocked')
            ), 1), else_=0)),
            func.sum(case((scope.c.coverage_status == 'uncovered', 1), else_=0)),
        ).select_from(scope)
    ).one()
    options = session.execute(
        select(scope.c.environment, scope.c.coverage_status).distinct()
    ).all()
    environment_options = sorted({
        get_environment_label(value) for value, _state in options
    })
    status_options = [
        name for name in ('ready', 'degraded', 'validation_required', 'blocked', 'uncovered')
        if any(state == name for _value, state in options)
    ]

    statement = select(scope)
    if environment:
        by_label = {get_environment_label(raw): raw for raw, _label in ENVIRONMENTS}
        normalized = by_label.get(environment, environment)
        statement = statement.where(scope.c.environment == normalized)
    if status:
        statement = statement.where(scope.c.coverage_status == status)
    if query.strip():
        term = f'%{query.strip().lower()}%'
        statement = statement.where(or_(
            func.lower(scope.c.asset_name).like(term),
            func.lower(scope.c.asset_key).like(term),
            func.lower(scope.c.environment).like(term),
            func.lower(func.replace(scope.c.environment, '_', ' ')).like(term),
            func.lower(func.coalesce(scope.c.source_name, '')).like(term),
            func.lower(scope.c.hint).like(term),
            func.lower(func.replace(scope.c.coverage_status, '_', ' ')).like(term),
            func.lower(case(
                (scope.c.coverage_status == 'uncovered', 'Not Bound'),
                (scope.c.coverage_status == 'validation_required', 'Binding Validation Required'),
                else_=scope.c.coverage_status,
            )).like(term),
        ))
    filtered_count = int(session.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    ) or 0)
    window = build_pagination_window(total_items=filtered_count, page=page, per_page=per_page)
    selected = session.execute(
        statement.order_by(scope.c.position, scope.c.asset_name, scope.c.asset_key)
        .offset(window.offset).limit(window.per_page)
    ).mappings().all()
    return {
        'rows': [dict(row) for row in selected],
        'pagination': pagination_payload(window),
        'stats': {
            'total': int(total or 0),
            'ready': int(ready or 0),
            'attention': int(attention or 0),
            'uncovered': int(uncovered or 0),
        },
        'environment_options': environment_options,
        'status_options': status_options,
    }
