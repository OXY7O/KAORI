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


def _provider_model(provider_type: str):
    if provider_type == 'prometheus':
        return PrometheusInstance
    if provider_type == 'alertmanager':
        return AlertmanagerInstance
    if provider_type == 'kubernetes':
        return KubernetesConnection
    return None


def _candidate_target_ids(orphan: IntegrationInstance) -> dict[int, list[str]]:
    """Collect deterministic evidence that links an orphan identity to one canonical target."""
    model = _provider_model(orphan.provider_type)
    if model is None:
        return {}

    evidence: dict[int, list[str]] = {}

    def add(target_id: int | None, reason: str) -> None:
        if target_id is None or target_id == orphan.id:
            return
        target = db.session.get(IntegrationInstance, target_id)
        if target is None or target.provider_type != orphan.provider_type:
            return
        evidence.setdefault(target_id, []).append(reason)

    metadata = orphan.metadata_json or {}
    provider_record_id = metadata.get('provider_record_id')
    if provider_record_id is not None and orphan.provider_type != 'kubernetes':
        provider_record = db.session.get(model, provider_record_id)
        add(
            getattr(provider_record, 'integration_instance_id', None) if provider_record else None,
            f'metadata.provider_record_id={provider_record_id}',
        )

    asset_key = metadata.get('asset_key')
    if orphan.provider_type == 'kubernetes' and asset_key:
        connection = db.session.execute(
            select(KubernetesConnection).where(KubernetesConnection.cluster_id == str(asset_key))
        ).scalar_one_or_none()
        add(
            connection.integration_instance_id if connection else None,
            f'metadata.asset_key={asset_key}',
        )

    # Runtime observations retain the provider record id in instance_id. This is
    # the strongest recovery signal for duplicate identities created before the
    # canonical FK was made authoritative.
    observation_instance_ids = set(
        db.session.execute(
            select(IntegrationRuntimeObservation.instance_id).where(
                IntegrationRuntimeObservation.integration_instance_id == orphan.id,
                IntegrationRuntimeObservation.provider == orphan.provider_type,
            )
        ).scalars()
    )
    for instance_id in observation_instance_ids:
        if orphan.provider_type == 'kubernetes':
            provider_record = db.session.execute(
                select(KubernetesConnection).where(KubernetesConnection.cluster_id == str(instance_id))
            ).scalar_one_or_none()
        else:
            try:
                provider_record = db.session.get(model, int(instance_id))
            except (TypeError, ValueError):
                provider_record = None
        add(
            getattr(provider_record, 'integration_instance_id', None) if provider_record else None,
            f'runtime_observation.instance_id={instance_id}',
        )

    orphan_bindings = db.session.execute(
        select(IntegrationBinding).where(IntegrationBinding.integration_instance_id == orphan.id)
    ).scalars().all()
    for binding in orphan_bindings:
        if orphan.provider_type == 'kubernetes' and binding.asset_type == 'kubernetes_cluster':
            connection = db.session.execute(
                select(KubernetesConnection).where(KubernetesConnection.cluster_id == binding.asset_key)
            ).scalar_one_or_none()
            add(
                connection.integration_instance_id if connection else None,
                f'binding:{binding.id} asset={binding.asset_type}/{binding.asset_key}',
            )
            continue

        canonical_binding_ids = db.session.execute(
            select(IntegrationBinding.integration_instance_id).where(
                IntegrationBinding.asset_type == binding.asset_type,
                IntegrationBinding.asset_key == binding.asset_key,
                IntegrationBinding.integration_instance_id != orphan.id,
            )
        ).scalars().all()
        for target_id in canonical_binding_ids:
            add(target_id, f'matching binding asset={binding.asset_type}/{binding.asset_key}')

    # Name matching is a final, weaker signal. It is only accepted when it
    # resolves to exactly one canonical provider record.
    if orphan.provider_type in {'prometheus', 'alertmanager'}:
        provider_rows = db.session.execute(select(model).where(model.name == orphan.name)).scalars().all()
        matching_ids = {
            row.integration_instance_id
            for row in provider_rows
            if row.integration_instance_id and row.integration_instance_id != orphan.id
        }
        if len(matching_ids) == 1:
            add(matching_ids.pop(), f'exact provider name={orphan.name!r}')
    elif orphan.provider_type == 'kubernetes':
        connections = db.session.execute(select(KubernetesConnection)).scalars().all()
        matching_ids = {
            row.integration_instance_id
            for row in connections
            if row.integration_instance
            and row.integration_instance_id != orphan.id
            and row.integration_instance.name == orphan.name
        }
        if len(matching_ids) == 1:
            add(matching_ids.pop(), f'exact canonical name={orphan.name!r}')

    return evidence


def _provider_target(orphan: IntegrationInstance) -> tuple[IntegrationInstance | None, dict[int, list[str]]]:
    evidence = _candidate_target_ids(orphan)
    if len(evidence) != 1:
        return None, evidence
    target_id = next(iter(evidence))
    return db.session.get(IntegrationInstance, target_id), evidence

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
        target, target_evidence = _provider_target(orphan)
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
        evidence_text = {
            target_id: reasons for target_id, reasons in sorted(target_evidence.items())
        }
        blockers.append(
            f'IntegrationInstance {orphan.id} ({orphan.provider_type}/{orphan.name}) has '
            f'{len(binding_count)} binding(s) and {len(observation_count)} observation(s), but no unambiguous provider target. '
            f'Candidate evidence: {evidence_text or "none"}.'
        )

    for provider, spec in LEGACY_PROVIDER_TABLES.items():
        binding_table = _table(spec['binding'])
        if binding_table is not None:
            rows = [dict(row) for row in db.session.execute(select(binding_table)).mappings().all()]
            unrecoverable: list[int] = []
            created_count = 0
            for row in rows:
                provider_model = PrometheusInstance if provider == 'prometheus' else AlertmanagerInstance
                provider_record = db.session.get(provider_model, row[spec['binding_fk']])
                canonical_id = getattr(provider_record, 'integration_instance_id', None) if provider_record else None
                if canonical_id is None:
                    unrecoverable.append(row['id'])
                    continue
                existing = db.session.execute(
                    select(IntegrationBinding).where(
                        IntegrationBinding.integration_instance_id == canonical_id,
                        IntegrationBinding.asset_type == row['scope_type'],
                        IntegrationBinding.asset_key == str(row['scope_key']),
                        IntegrationBinding.binding_role == (row.get('binding_role') or 'primary'),
                    )
                ).scalar_one_or_none()
                if existing is None:
                    created_count += 1
                    actions.append(
                        ReconcileAction(
                            action='create_canonical_binding_from_legacy',
                            subject=f'{spec["binding"]}:{row["id"]}',
                            details={
                                'integration_instance_id': canonical_id,
                                'asset_type': row['scope_type'],
                                'asset_key': str(row['scope_key']),
                                'binding_role': row.get('binding_role') or 'primary',
                            },
                        )
                    )
                    if apply:
                        default_scope = (
                            ['metrics', 'capacity', 'utilization', 'storage', 'workload', 'forecast', 'top_consumers', 'alert_metrics']
                            if provider == 'prometheus'
                            else ['alerts', 'alerts_v2', 'silences', 'silences_v2', 'routing', 'receivers', 'status_v2']
                        )
                        db.session.add(
                            IntegrationBinding(
                                integration_instance_id=canonical_id,
                                asset_type=row['scope_type'],
                                asset_key=str(row['scope_key']),
                                binding_role=row.get('binding_role') or 'primary',
                                priority=row.get('priority') or 100,
                                enabled=bool(row.get('enabled', True)),
                                capability_scope=default_scope,
                            )
                        )
            if unrecoverable:
                blockers.append(f'{spec["binding"]} rows have no canonical provider identity: {unrecoverable}')
            elif rows:
                actions.append(
                    ReconcileAction(
                        action='delete_verified_legacy_bindings',
                        subject=spec['binding'],
                        details={'count': len(rows), 'canonical_bindings_created': created_count},
                    )
                )
                if apply:
                    db.session.flush()
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
