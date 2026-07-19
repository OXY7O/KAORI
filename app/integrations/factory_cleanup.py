from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.extensions.db import db
from app.models import (
    AlertmanagerBinding,
    AlertmanagerConfig,
    AlertmanagerInstance,
    Cluster,
    PrometheusBinding,
    PrometheusConfig,
    PrometheusInstance,
)
from app.models.integration import IntegrationBinding, IntegrationInstance, KubernetesConnection
from app.models.integration_runtime import IntegrationRuntimeObservation


@dataclass(slots=True)
class CleanupAction:
    key: str
    count: int
    detail: str


@dataclass(slots=True)
class CleanupReport:
    can_apply: bool
    applied: bool = False
    actions: list[CleanupAction] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    preserved_cluster_ids: list[str] = field(default_factory=list)
    recreated_kubernetes_connection_ids: list[int] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            'can_apply': self.can_apply,
            'applied': self.applied,
            'actions': [asdict(action) for action in self.actions],
            'blockers': self.blockers,
            'preserved_cluster_ids': self.preserved_cluster_ids,
            'recreated_kubernetes_connection_ids': self.recreated_kubernetes_connection_ids,
        }


@dataclass(frozen=True, slots=True)
class KubernetesSnapshot:
    cluster_id: str
    kubeconfig: str
    verify_ssl: bool
    allow_weak_tls: bool
    server: str | None


def _count(model: type[db.Model]) -> int:
    return int(db.session.query(model).count())


def _connection_snapshots(clusters: list[Cluster]) -> tuple[list[KubernetesSnapshot], list[str]]:
    snapshots: list[KubernetesSnapshot] = []
    blockers: list[str] = []
    for cluster in clusters:
        connection = KubernetesConnection.query.filter_by(cluster_id=cluster.id).first()
        kubeconfig = (connection.kubeconfig if connection else None) or cluster.kubeconfig
        if not kubeconfig:
            blockers.append(
                f'Cluster {cluster.id} ({cluster.name}) has no kubeconfig in KubernetesConnection or legacy cluster storage.'
            )
            continue
        snapshots.append(
            KubernetesSnapshot(
                cluster_id=cluster.id,
                kubeconfig=kubeconfig,
                verify_ssl=connection.verify_ssl if connection else cluster.kube_verify_ssl,
                allow_weak_tls=connection.allow_weak_tls if connection else cluster.kube_allow_weak_tls,
                server=(connection.server if connection else None) or cluster.server,
            )
        )
    return snapshots, blockers


def build_factory_cleanup_report(*, apply: bool = False) -> CleanupReport:
    """Reset all integration runtime data and rebuild Kubernetes as canonical integrations.

    Infrastructure assets are preserved. Prometheus and Alertmanager must be registered again.
    The operation is intentionally all-or-nothing.
    """

    clusters = Cluster.query.order_by(Cluster.created_at.asc(), Cluster.id.asc()).all()
    snapshots, blockers = _connection_snapshots(clusters)

    actions = [
        CleanupAction('delete_runtime_observations', _count(IntegrationRuntimeObservation), 'All persisted integration runtime observations.'),
        CleanupAction('delete_canonical_bindings', _count(IntegrationBinding), 'All provider-neutral runtime-to-asset mappings.'),
        CleanupAction('delete_legacy_prometheus_bindings', _count(PrometheusBinding), 'Legacy Prometheus bindings.'),
        CleanupAction('delete_legacy_alertmanager_bindings', _count(AlertmanagerBinding), 'Legacy Alertmanager bindings.'),
        CleanupAction('delete_prometheus_instances', _count(PrometheusInstance), 'All Prometheus and Thanos runtimes; add them again after cleanup.'),
        CleanupAction('delete_alertmanager_instances', _count(AlertmanagerInstance), 'All Alertmanager runtimes; add them again after cleanup.'),
        CleanupAction('delete_legacy_prometheus_configs', _count(PrometheusConfig), 'Legacy cluster-scoped Prometheus configuration.'),
        CleanupAction('delete_legacy_alertmanager_configs', _count(AlertmanagerConfig), 'Legacy cluster-scoped Alertmanager configuration.'),
        CleanupAction('rebuild_kubernetes_connections', len(snapshots), 'Recreate one canonical Kubernetes integration per preserved cluster.'),
        CleanupAction('delete_orphan_canonical_instances', _count(IntegrationInstance), 'Replace the canonical integration registry with clean Kubernetes identities.'),
    ]
    report = CleanupReport(
        can_apply=not blockers,
        actions=actions,
        blockers=blockers,
        preserved_cluster_ids=[cluster.id for cluster in clusters],
    )
    if not apply or blockers:
        return report

    try:
        # Child/provider records first; canonical identities last.
        IntegrationRuntimeObservation.query.delete(synchronize_session=False)
        IntegrationBinding.query.delete(synchronize_session=False)
        PrometheusBinding.query.delete(synchronize_session=False)
        AlertmanagerBinding.query.delete(synchronize_session=False)
        PrometheusConfig.query.delete(synchronize_session=False)
        AlertmanagerConfig.query.delete(synchronize_session=False)
        PrometheusInstance.query.delete(synchronize_session=False)
        AlertmanagerInstance.query.delete(synchronize_session=False)
        KubernetesConnection.query.delete(synchronize_session=False)
        db.session.flush()
        IntegrationInstance.query.delete(synchronize_session=False)
        db.session.flush()

        cluster_by_id = {cluster.id: cluster for cluster in clusters}
        for snapshot in snapshots:
            cluster = cluster_by_id[snapshot.cluster_id]
            canonical = IntegrationInstance(
                provider_type='kubernetes',
                name=f'{cluster.name} Kubernetes API',
                description=f'Canonical Kubernetes API connection for {cluster.name}.',
                environment=cluster.environment,
                enabled=True,
                lifecycle_status=cluster.kubernetes_lifecycle_status or 'active',
                readiness_status=cluster.kubernetes_readiness_status or 'validation_required',
                health_status='healthy' if cluster.status == 'connected' else 'not_observed',
                last_checked_at=cluster.kubernetes_last_validated_at or cluster.last_check,
                metadata_json={'asset_type': 'kubernetes_cluster', 'asset_key': cluster.id},
            )
            db.session.add(canonical)
            db.session.flush()

            connection = KubernetesConnection(
                integration_instance_id=canonical.id,
                cluster_id=cluster.id,
                kubeconfig=snapshot.kubeconfig,
                verify_ssl=snapshot.verify_ssl,
                allow_weak_tls=snapshot.allow_weak_tls,
                server=snapshot.server,
                compatibility_profile=cluster.kubernetes_compatibility_profile,
                readiness_status=cluster.kubernetes_readiness_status or 'validation_required',
                validation_message=cluster.kubernetes_validation_message,
                last_validated_at=cluster.kubernetes_last_validated_at,
                discovery_summary=cluster.kubernetes_api_discovery_summary,
            )
            db.session.add(connection)
            db.session.add(
                IntegrationBinding(
                    integration_instance_id=canonical.id,
                    asset_type='kubernetes_cluster',
                    asset_key=cluster.id,
                    binding_role='primary',
                    priority=100,
                    enabled=True,
                    capability_scope=['inventory', 'operations', 'governance', 'analytics_asset'],
                )
            )
            # Remove the credential duplicate; canonical connection is authoritative.
            cluster.kubeconfig = None
            db.session.flush()
            report.recreated_kubernetes_connection_ids.append(connection.id)

        db.session.commit()
        report.applied = True
        return report
    except Exception:
        db.session.rollback()
        raise
