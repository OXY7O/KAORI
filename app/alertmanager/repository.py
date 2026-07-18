from __future__ import annotations

from sqlalchemy import select

from app.extensions import db
from app.models.alertmanager import AlertmanagerBinding, AlertmanagerConfig, AlertmanagerInstance


def list_instances() -> list[AlertmanagerInstance]:
    statement = select(AlertmanagerInstance).order_by(AlertmanagerInstance.name.asc())
    return list(db.session.execute(statement).scalars().all())


def get_instance(instance_id: int) -> AlertmanagerInstance | None:
    return db.session.get(AlertmanagerInstance, instance_id)


def get_instance_by_name(name: str) -> AlertmanagerInstance | None:
    statement = select(AlertmanagerInstance).where(AlertmanagerInstance.name == name)
    return db.session.execute(statement).scalar_one_or_none()


def get_legacy_config_by_cluster_id(cluster_id: str) -> AlertmanagerConfig | None:
    statement = select(AlertmanagerConfig).where(AlertmanagerConfig.cluster_id == cluster_id)
    return db.session.execute(statement).scalar_one_or_none()


def list_bindings_for_instance(instance_id: int) -> list[AlertmanagerBinding]:
    statement = (
        select(AlertmanagerBinding)
        .where(AlertmanagerBinding.alertmanager_instance_id == instance_id)
        .order_by(AlertmanagerBinding.priority.asc(), AlertmanagerBinding.id.asc())
    )
    return list(db.session.execute(statement).scalars().all())


def get_binding(binding_id: int) -> AlertmanagerBinding | None:
    return db.session.get(AlertmanagerBinding, binding_id)


def list_bindings_for_scope(
    *,
    scope_type: str,
    scope_key: str,
) -> list[AlertmanagerBinding]:
    statement = (
        select(AlertmanagerBinding)
        .join(AlertmanagerBinding.instance)
        .where(
            AlertmanagerBinding.scope_type == scope_type,
            AlertmanagerBinding.scope_key == scope_key,
            AlertmanagerBinding.enabled.is_(True),
            AlertmanagerInstance.enabled.is_(True),
        )
    )
    return list(db.session.execute(statement).scalars().all())


def find_binding(
    *,
    instance_id: int,
    scope_type: str,
    scope_key: str,
) -> AlertmanagerBinding | None:
    statement = select(AlertmanagerBinding).where(
        AlertmanagerBinding.alertmanager_instance_id == instance_id,
        AlertmanagerBinding.scope_type == scope_type,
        AlertmanagerBinding.scope_key == scope_key,
    )
    return db.session.execute(statement).scalar_one_or_none()


def resolve_instances_for_scope(
    *,
    scope_type: str,
    scope_key: str,
) -> list[AlertmanagerInstance]:
    # Compatibility helper. New consumers should use
    # alertmanager.resolver.resolve_alertmanager_sources().
    role_order = {'primary': 0, 'secondary': 1, 'fallback': 2}
    bindings = list_bindings_for_scope(scope_type=scope_type, scope_key=scope_key)
    bindings.sort(
        key=lambda item: (
            role_order.get(item.binding_role, 9),
            item.priority,
            item.id,
        )
    )
    return [binding.instance for binding in bindings]


def count_bindings_by_scope_type() -> dict[str, int]:
    counts: dict[str, int] = {}
    for binding in db.session.execute(select(AlertmanagerBinding)).scalars():
        counts[binding.scope_type] = counts.get(binding.scope_type, 0) + 1
    return counts
