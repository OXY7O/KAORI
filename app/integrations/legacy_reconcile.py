from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import delete, inspect, select, update

from app.extensions.db import db
from app.models import (
    AlertmanagerInstance,
    Cluster,
    IntegrationBinding,
    IntegrationInstance,
    IntegrationRuntimeObservation,
    KubernetesConnection,
    PrometheusInstance,
)


LEGACY_PROVIDER_TABLES: dict[str, dict[str, str]] = {
    'prometheus': {
        'config': 'prometheus_configs',
        'binding': 'prometheus_bindings',
        'instance': 'prometheus_instances',
        'binding_fk': 'prometheus_instance_id',
    },
    'alertmanager': {
        'config': 'alertmanager_configs',
        'binding': 'alertmanager_bindings',
        'instance': 'alertmanager_instances',
        'binding_fk': 'alertmanager_instance_id',
    },
}


@dataclass(frozen=True)
class ReconcileAction:
    action: str
    subject: str
    details: dict[str, Any]


@dataclass(frozen=True)
class ReconcileReport:
    can_apply: bool
    applied: bool
    actions: tuple[ReconcileAction, ...]
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            'can_apply': self.can_apply,
            'applied': self.applied,
            'actions': [asdict(action) for action in self.actions],
            'blockers': list(self.blockers),
        }


def _table(name: str):
    if not inspect(db.engine).has_table(name):
        return None
    table = db.metadata.tables.get(name)
    if table is None:
        table = db.Table(name, db.metadata, autoload_with=db.engine)
    return table


def _provider_target(orphan: IntegrationInstance) -> IntegrationInstance | None:
    metadata = orphan.metadata_json or {}
    provider_record_id = metadata.get('provider_record_id')

    if orphan.provider_type == 'prometheus':
        model = PrometheusInstance
    elif orphan.provider_type == 'alertmanager':
        model = AlertmanagerInstance
    elif orphan.provider_type == 'kubernetes':
        model = KubernetesConnection
    else:
        return None

    provider_record = None
    if provider_record_id is not None and orphan.provider_type != 'kubernetes':
        provider_record = db.session.get(model, provider_record_id)
    elif orphan.provider_type == 'kubernetes':
        asset_key = metadata.get('asset_key')
        if asset_key:
            provider_record = db.session.execute(
                select(KubernetesConnection).where(KubernetesConnection.cluster_id == str(asset_key))
            ).scalar_one_or_none()

    if provider_record is not None:
        canonical_id = getattr(provider_record, 'integration_instance_id', None)
        if canonical_id and canonical_id != orphan.id:
            return db.session.get(IntegrationInstance, canonical_id)

    if orphan.provider_type in {'prometheus', 'alertmanager'}:
        provider_rows = db.session.execute(select(model).where(model.name == orphan.name)).scalars().all()
        targets = {
            row.integration_instance_id
            for row in provider_rows
            if row.integration_instance_id and row.integration_instance_id != orphan.id
        }
        if len(targets) == 1:
            return db.session.get(IntegrationInstance, targets.pop())

    return None


def _merge_capabilities(left: list[str] | None, right: list[str] | None) -> list[str] | None:
    values = sorted(set(left or []) | set(right or []))
    return values or None


def _merge_orphan(orphan: IntegrationInstance, target: IntegrationInstance, *, apply: bool) -> list[ReconcileAction]:
    actions: list[ReconcileAction] = []
    orphan_bindings = db.session.execute(
        select(IntegrationBinding).where(IntegrationBinding.integration_instance_id == orphan.id)
    ).scalars().all()

    for binding in orphan_bindings:
        duplicate = db.session.execute(
            select(IntegrationBinding).where(
                IntegrationBinding.integration_instance_id == target.id,
                IntegrationBinding.asset_type == binding.asset_type,
                IntegrationBinding.asset_key == binding.asset_key,
                IntegrationBinding.binding_role == binding.binding_role,
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            actions.append(
                ReconcileAction(
                    action='merge_duplicate_binding',
                    subject=f'integration_binding:{binding.id}',
                    details={'target_binding_id': duplicate.id, 'target_integration_instance_id': target.id},
                )
            )
            if apply:
                duplicate.priority = min(duplicate.priority, binding.priority)
                duplicate.enabled = duplicate.enabled or binding.enabled
                duplicate.capability_scope = _merge_capabilities(
                    duplicate.capability_scope, binding.capability_scope
                )
                db.session.delete(binding)
        else:
            actions.append(
                ReconcileAction(
                    action='move_binding',
                    subject=f'integration_binding:{binding.id}',
                    details={'from': orphan.id, 'to': target.id},
                )
            )
            if apply:
                binding.integration_instance_id = target.id

    observation_count = db.session.execute(
        select(IntegrationRuntimeObservation.id).where(
            IntegrationRuntimeObservation.integration_instance_id == orphan.id
        )
    ).scalars().all()
    if observation_count:
        actions.append(
            ReconcileAction(
                action='move_runtime_observations',
                subject=f'integration_instance:{orphan.id}',
                details={'count': len(observation_count), 'to': target.id},
            )
        )
        if apply:
            db.session.execute(
                update(IntegrationRuntimeObservation)
                .where(IntegrationRuntimeObservation.integration_instance_id == orphan.id)
                .values(integration_instance_id=target.id)
            )

    actions.append(
        ReconcileAction(
            action='delete_merged_orphan',
            subject=f'integration_instance:{orphan.id}',
            details={'provider_type': orphan.provider_type, 'name': orphan.name, 'merged_into': target.id},
        )
    )
    if apply:
        db.session.delete(orphan)
    return actions


def _legacy_binding_verified(provider: str, row: dict[str, Any]) -> bool:
    spec = LEGACY_PROVIDER_TABLES[provider]
    if provider == 'prometheus':
        provider_model = PrometheusInstance
    else:
        provider_model = AlertmanagerInstance

    provider_record = db.session.get(provider_model, row[spec['binding_fk']])
    if provider_record is None or provider_record.integration_instance_id is None:
        return False
    return db.session.execute(
        select(IntegrationBinding.id).where(
            IntegrationBinding.integration_instance_id == provider_record.integration_instance_id,
            IntegrationBinding.asset_type == row['scope_type'],
            IntegrationBinding.asset_key == str(row['scope_key']),
        )
    ).first() is not None


def _legacy_config_verified(provider: str, row: dict[str, Any]) -> bool:
    cluster_id = str(row['cluster_id'])
    provider_model = PrometheusInstance if provider == 'prometheus' else AlertmanagerInstance
    canonical_ids = db.session.execute(
        select(provider_model.integration_instance_id).where(
            provider_model.integration_instance_id.is_not(None)
        )
    ).scalars().all()
    if not canonical_ids:
        return False
    return db.session.execute(
        select(IntegrationBinding.id).where(
            IntegrationBinding.integration_instance_id.in_(canonical_ids),
            IntegrationBinding.asset_type == 'kubernetes_cluster',
            IntegrationBinding.asset_key == cluster_id,
            IntegrationBinding.enabled.is_(True),
        )
    ).first() is not None


def build_reconciliation_report(*, apply: bool = False) -> ReconcileReport:
    actions: list[ReconcileAction] = []
    blockers: list[str] = []

    provider_identity_ids = set(
        db.session.execute(
            select(PrometheusInstance.integration_instance_id).where(
                PrometheusInstance.integration_instance_id.is_not(None)
            )
        ).scalars()
    )
    provider_identity_ids.update(
        db.session.execute(
            select(AlertmanagerInstance.integration_instance_id).where(
                AlertmanagerInstance.integration_instance_id.is_not(None)
            )
        ).scalars()
    )
    provider_identity_ids.update(
        db.session.execute(select(KubernetesConnection.integration_instance_id)).scalars()
    )
    all_instances = db.session.execute(select(IntegrationInstance).order_by(IntegrationInstance.id)).scalars().all()
    orphans = [row for row in all_instances if row.id not in provider_identity_ids]

    for orphan in orphans:
        target = _provider_target(orphan)
        binding_count = db.session.execute(
            select(IntegrationBinding.id).where(IntegrationBinding.integration_instance_id == orphan.id)
        ).scalars().all()
        observation_count = db.session.execute(
            select(IntegrationRuntimeObservation.id).where(
                IntegrationRuntimeObservation.integration_instance_id == orphan.id
            )
        ).scalars().all()

        if target is not None:
            actions.extend(_merge_orphan(orphan, target, apply=apply))
            continue
        if not binding_count and not observation_count:
            actions.append(
                ReconcileAction(
                    action='delete_empty_orphan',
                    subject=f'integration_instance:{orphan.id}',
                    details={'provider_type': orphan.provider_type, 'name': orphan.name},
                )
            )
            if apply:
                db.session.delete(orphan)
            continue
        blockers.append(
            f'IntegrationInstance {orphan.id} ({orphan.provider_type}/{orphan.name}) has '
            f'{len(binding_count)} binding(s) and {len(observation_count)} observation(s), but no unambiguous provider target.'
        )

    for provider, spec in LEGACY_PROVIDER_TABLES.items():
        binding_table = _table(spec['binding'])
        if binding_table is not None:
            rows = [dict(row) for row in db.session.execute(select(binding_table)).mappings().all()]
            unverified = [row['id'] for row in rows if not _legacy_binding_verified(provider, row)]
            if unverified:
                blockers.append(f'{spec["binding"]} rows cannot be reconciled: {unverified}')
            elif rows:
                actions.append(
                    ReconcileAction(
                        action='delete_verified_legacy_bindings',
                        subject=spec['binding'],
                        details={'count': len(rows)},
                    )
                )
                if apply:
                    db.session.execute(delete(binding_table))

        config_table = _table(spec['config'])
        if config_table is not None:
            rows = [dict(row) for row in db.session.execute(select(config_table)).mappings().all()]
            unverified = [row['id'] for row in rows if not _legacy_config_verified(provider, row)]
            if unverified:
                blockers.append(f'{spec["config"]} rows cannot be reconciled: {unverified}')
            elif rows:
                actions.append(
                    ReconcileAction(
                        action='delete_verified_legacy_configs',
                        subject=spec['config'],
                        details={'count': len(rows)},
                    )
                )
                if apply:
                    db.session.execute(delete(config_table))

    clusters = db.session.execute(select(Cluster).order_by(Cluster.id)).scalars().all()
    for cluster in clusters:
        legacy_value = getattr(cluster, 'kubeconfig', None)
        if not legacy_value:
            continue
        connection = db.session.execute(
            select(KubernetesConnection).where(KubernetesConnection.cluster_id == cluster.id)
        ).scalar_one_or_none()
        if connection is None or not connection.kubeconfig:
            blockers.append(
                f'Cluster {cluster.id} still has legacy kubeconfig data but no non-empty canonical KubernetesConnection.'
            )
            continue
        actions.append(
            ReconcileAction(
                action='clear_verified_legacy_kubeconfig',
                subject=f'cluster:{cluster.id}',
                details={'kubernetes_connection_id': connection.id},
            )
        )
        if apply:
            cluster.kubeconfig = None

    can_apply = not blockers
    if apply:
        if blockers:
            db.session.rollback()
        else:
            db.session.commit()

    return ReconcileReport(
        can_apply=can_apply,
        applied=bool(apply and can_apply),
        actions=tuple(actions),
        blockers=tuple(blockers),
    )
