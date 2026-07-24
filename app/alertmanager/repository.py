from __future__ import annotations

from sqlalchemy import func, select

from app.extensions.db import db
from app.models.alertmanager import AlertmanagerInstance
from app.models.integration import IntegrationBinding, IntegrationInstance

PROVIDER_TYPE = 'alertmanager'


def list_instances() -> list[AlertmanagerInstance]:
    statement = (
        select(AlertmanagerInstance)
        .join(AlertmanagerInstance.integration_instance)
        .order_by(IntegrationInstance.name.asc())
    )
    return list(db.session.execute(statement).scalars().all())


def get_instance(instance_id: int) -> AlertmanagerInstance | None:
    return db.session.get(AlertmanagerInstance, instance_id)


def get_instance_by_name(name: str) -> AlertmanagerInstance | None:
    statement = (
        select(AlertmanagerInstance)
        .join(AlertmanagerInstance.integration_instance)
        .where(
            IntegrationInstance.provider_type == PROVIDER_TYPE,
            IntegrationInstance.name == name,
        )
    )
    return db.session.execute(statement).scalar_one_or_none()


def list_bindings_for_instance(instance_id: int) -> list[IntegrationBinding]:
    instance = get_instance(instance_id)
    if instance is None or instance.integration_instance_id is None:
        return []
    statement = (
        select(IntegrationBinding)
        .where(IntegrationBinding.integration_instance_id == instance.integration_instance_id)
        .order_by(IntegrationBinding.priority.asc(), IntegrationBinding.id.asc())
    )
    return list(db.session.execute(statement).scalars().all())


def get_binding(binding_id: int) -> IntegrationBinding | None:
    statement = (
        select(IntegrationBinding)
        .join(IntegrationBinding.instance)
        .where(
            IntegrationBinding.id == binding_id,
            IntegrationInstance.provider_type == PROVIDER_TYPE,
        )
    )
    return db.session.execute(statement).scalar_one_or_none()


def list_bindings_for_scope(*, scope_type: str, scope_key: str) -> list[IntegrationBinding]:
    statement = (
        select(IntegrationBinding)
        .join(IntegrationBinding.instance)
        .where(
            IntegrationBinding.asset_type == scope_type,
            IntegrationBinding.asset_key == str(scope_key),
            IntegrationBinding.enabled.is_(True),
            IntegrationInstance.provider_type == PROVIDER_TYPE,
            IntegrationInstance.enabled.is_(True),
        )
    )
    return list(db.session.execute(statement).scalars().all())


def find_binding(*, instance_id: int, scope_type: str, scope_key: str) -> IntegrationBinding | None:
    instance = get_instance(instance_id)
    if instance is None or instance.integration_instance_id is None:
        return None
    statement = (
        select(IntegrationBinding)
        .where(
            IntegrationBinding.integration_instance_id == instance.integration_instance_id,
            IntegrationBinding.asset_type == scope_type,
            IntegrationBinding.asset_key == str(scope_key),
        )
        .order_by(IntegrationBinding.id.asc())
    )
    return db.session.execute(statement).scalars().first()


def provider_instance_for_binding(binding: IntegrationBinding) -> AlertmanagerInstance | None:
    return AlertmanagerInstance.query.filter_by(
        integration_instance_id=binding.integration_instance_id,
    ).first()


def resolve_instances_for_scope(*, scope_type: str, scope_key: str) -> list[AlertmanagerInstance]:
    role_order = {'primary': 0, 'secondary': 1, 'fallback': 2}
    bindings = list_bindings_for_scope(scope_type=scope_type, scope_key=scope_key)
    bindings.sort(key=lambda item: (role_order.get(item.binding_role, 9), item.priority, item.id))
    instances: list[AlertmanagerInstance] = []
    for binding in bindings:
        instance = provider_instance_for_binding(binding)
        if instance is not None:
            instances.append(instance)
    return instances


def count_bindings_by_scope_type() -> dict[str, int]:
    statement = (
        select(IntegrationBinding.asset_type, func.count(IntegrationBinding.id))
        .join(IntegrationBinding.instance)
        .where(IntegrationInstance.provider_type == PROVIDER_TYPE)
        .group_by(IntegrationBinding.asset_type)
    )
    return {scope_type: int(count) for scope_type, count in db.session.execute(statement).all()}
