from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, inspect, select

from app.extensions.db import db
from app.models import (
    AlertmanagerInstance,
    Cluster,
    IntegrationBinding,
    IntegrationInstance,
    KubernetesConnection,
    PrometheusInstance,
)

LEGACY_TABLES = (
    'prometheus_configs',
    'prometheus_bindings',
    'alertmanager_configs',
    'alertmanager_bindings',
)

ACTIVE_SOURCE_PATTERNS: dict[str, tuple[str, ...]] = {
    'legacy_prometheus_model': (
        'PrometheusConfig.query',
        'db.session.query(PrometheusConfig',
        'select(PrometheusConfig',
        'getattr(cluster, \'prometheus_config\'',
        'cluster.prometheus_config',
    ),
    'legacy_alertmanager_model': (
        'AlertmanagerConfig.query',
        'db.session.query(AlertmanagerConfig',
        'select(AlertmanagerConfig',
        'getattr(cluster, \'alertmanager_config\'',
        'cluster.alertmanager_config',
        'get_legacy_config_by_cluster_id',
    ),
    'provider_specific_binding_model': (
        'PrometheusBinding.query',
        'AlertmanagerBinding.query',
        'select(PrometheusBinding',
        'select(AlertmanagerBinding',
    ),
    'legacy_cluster_kubeconfig': (
        'cluster.kubeconfig',
        'getattr(cluster, \'kubeconfig\'',
    ),
}

EXCLUDED_SOURCE_PARTS = {
    '__pycache__',
    'migrations',
    'tests',
}
EXCLUDED_SOURCE_FILES = {
    'app/models/prometheus.py',
    'app/models/alertmanager.py',
    'app/models/cluster.py',
    'app/models/__init__.py',
    'app/integrations/legacy_audit.py',
}


@dataclass(frozen=True)
class AuditCheck:
    key: str
    status: str
    summary: str
    details: dict[str, Any]
    destructive_blocker: bool = False


@dataclass(frozen=True)
class LegacyAuditReport:
    ready_for_schema_removal: bool
    checks: tuple[AuditCheck, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            'ready_for_schema_removal': self.ready_for_schema_removal,
            'checks': [asdict(check) for check in self.checks],
        }


def _status(*, passed: bool, warning: bool = False) -> str:
    if passed:
        return 'pass'
    return 'warning' if warning else 'fail'


def scan_active_source_references(project_root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    app_root = project_root / 'app'
    if not app_root.exists():
        return findings

    for path in sorted(app_root.rglob('*.py')):
        relative = path.relative_to(project_root).as_posix()
        if relative in EXCLUDED_SOURCE_FILES:
            continue
        if any(part in EXCLUDED_SOURCE_PARTS for part in path.parts):
            continue

        content = path.read_text(encoding='utf-8')
        for category, patterns in ACTIVE_SOURCE_PATTERNS.items():
            for pattern in patterns:
                if pattern not in content:
                    continue
                for line_number, line in enumerate(content.splitlines(), start=1):
                    if pattern in line:
                        findings.append(
                            {
                                'category': category,
                                'file': relative,
                                'line': line_number,
                                'pattern': pattern,
                                'excerpt': line.strip(),
                            }
                        )
    return findings


def _table_count(table_name: str) -> int | None:
    inspector = inspect(db.engine)
    if not inspector.has_table(table_name):
        return None
    table = db.metadata.tables.get(table_name)
    if table is None:
        table = db.Table(table_name, db.metadata, autoload_with=db.engine)
    return int(db.session.execute(select(func.count()).select_from(table)).scalar_one())


def _provider_instance_check(
    *,
    provider_type: str,
    model: type[PrometheusInstance] | type[AlertmanagerInstance],
) -> AuditCheck:
    rows = db.session.execute(select(model)).scalars().all()
    missing_identity = [row.id for row in rows if row.integration_instance_id is None]
    mismatched_identity: list[int] = []
    for row in rows:
        if row.integration_instance_id is None:
            continue
        canonical = db.session.get(IntegrationInstance, row.integration_instance_id)
        if canonical is None or canonical.provider_type != provider_type:
            mismatched_identity.append(row.id)

    passed = not missing_identity and not mismatched_identity
    return AuditCheck(
        key=f'{provider_type}_canonical_identity',
        status=_status(passed=passed),
        summary=(
            f'All {provider_type} provider records have a matching canonical identity.'
            if passed
            else f'{provider_type} provider records still have missing or mismatched canonical identities.'
        ),
        details={
            'provider_record_count': len(rows),
            'missing_integration_instance_ids': missing_identity,
            'mismatched_integration_instance_ids': mismatched_identity,
        },
        destructive_blocker=not passed,
    )


def build_legacy_audit_report(project_root: Path) -> LegacyAuditReport:
    checks: list[AuditCheck] = []

    findings = scan_active_source_references(project_root)
    checks.append(
        AuditCheck(
            key='active_source_references',
            status=_status(passed=not findings),
            summary=(
                'No active application source references legacy integration authorities.'
                if not findings
                else 'Active application source still references legacy integration authorities.'
            ),
            details={'finding_count': len(findings), 'findings': findings},
            destructive_blocker=bool(findings),
        )
    )

    legacy_counts = {table: _table_count(table) for table in LEGACY_TABLES}
    legacy_rows = {table: count for table, count in legacy_counts.items() if count not in (None, 0)}
    checks.append(
        AuditCheck(
            key='legacy_table_rows',
            status=_status(passed=not legacy_rows, warning=bool(legacy_rows)),
            summary=(
                'Legacy tables are empty or already absent.'
                if not legacy_rows
                else 'Legacy tables still contain rows that must be reconciled before removal.'
            ),
            details={'table_counts': legacy_counts},
            destructive_blocker=bool(legacy_rows),
        )
    )

    checks.append(
        _provider_instance_check(provider_type='prometheus', model=PrometheusInstance)
    )
    checks.append(
        _provider_instance_check(provider_type='alertmanager', model=AlertmanagerInstance)
    )

    clusters = db.session.execute(select(Cluster).order_by(Cluster.created_at, Cluster.id)).scalars().all()
    connections = {
        connection.cluster_id: connection
        for connection in db.session.execute(select(KubernetesConnection)).scalars().all()
    }
    missing_connections = [cluster.id for cluster in clusters if cluster.id not in connections]
    legacy_kubeconfig_clusters = [
        cluster.id for cluster in clusters if bool(getattr(cluster, 'kubeconfig', None))
    ]
    kube_passed = not missing_connections
    checks.append(
        AuditCheck(
            key='kubernetes_connection_coverage',
            status=_status(passed=kube_passed),
            summary=(
                'Every Kubernetes cluster has a canonical KubernetesConnection.'
                if kube_passed
                else 'Some Kubernetes clusters do not have a canonical KubernetesConnection.'
            ),
            details={
                'cluster_count': len(clusters),
                'missing_connection_cluster_ids': missing_connections,
                'clusters_with_legacy_kubeconfig_data': legacy_kubeconfig_clusters,
            },
            destructive_blocker=not kube_passed,
        )
    )

    integration_ids = set(db.session.execute(select(IntegrationInstance.id)).scalars())
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
    orphan_canonical_ids = sorted(integration_ids - provider_identity_ids)

    binding_rows = db.session.execute(select(IntegrationBinding)).scalars().all()
    orphan_binding_ids = [
        binding.id for binding in binding_rows if binding.integration_instance_id not in integration_ids
    ]
    integrity_passed = not orphan_canonical_ids and not orphan_binding_ids
    checks.append(
        AuditCheck(
            key='canonical_integrity',
            status=_status(passed=integrity_passed),
            summary=(
                'Canonical identities and bindings have no detected orphans.'
                if integrity_passed
                else 'Canonical identity or binding orphan records were detected.'
            ),
            details={
                'orphan_integration_instance_ids': orphan_canonical_ids,
                'orphan_integration_binding_ids': orphan_binding_ids,
            },
            destructive_blocker=not integrity_passed,
        )
    )

    ready = all(not check.destructive_blocker for check in checks)
    return LegacyAuditReport(ready_for_schema_removal=ready, checks=tuple(checks))
