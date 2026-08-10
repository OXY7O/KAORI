#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class VerificationError(RuntimeError):
    pass


def read(path: str) -> str:
    target = ROOT / path
    if not target.exists():
        raise VerificationError(f'Missing required file: {path}')
    return target.read_text(encoding='utf-8')


def require(path: str, *tokens: str) -> None:
    text = read(path)
    missing = [token for token in tokens if token not in text]
    if missing:
        raise VerificationError(f'{path} is missing: {missing}')


def main() -> int:
    require(
        'app/kubernetes_operations/configmaps/routes.py',
        "'kubernetes_configmap_created'",
        "'kubernetes_configmap_updated'",
        "'kubernetes_configmap_deleted'",
        'OperationalDeliveryPolicy.DECK_ON_FAILURE',
        'OperationalDeliveryPolicy.PERSISTENT',
        'record_operational_activity(',
    )
    require(
        'app/kubernetes_operations/secrets/route_support.py',
        'OperationalDeliveryPolicy.DECK_ON_FAILURE',
        'OperationalDeliveryPolicy.PERSISTENT',
        "event_type == 'kubernetes_secret_revealed'",
        'record_operational_activity(',
    )
    require(
        'app/kubernetes_operations/secrets/crud_routes.py',
        "'kubernetes_secret_created'",
        "'kubernetes_secret_data_replaced'",
        "'kubernetes_secret_deleted'",
    )
    require(
        'app/kubernetes_operations/secrets/tls_routes.py',
        "event_type='kubernetes_tls_secret_rotation'",
        "event_type='kubernetes_tls_secret_bulk_rotation'",
    )
    require(
        'app/governance/tls_certificates/routes.py',
        'record_operational_activity(',
        "event_type='governance_tls_secret_sync_dispatch'",
    )
    for path, tokens in {
        'app/cluster/routes.py': (
            "event_type='cluster_create'",
            "event_type='cluster_update'",
            "event_type='cluster_delete'",
        ),
        'app/prometheus/routes.py': (
            "event_type='prometheus_instance_created'",
            "event_type='prometheus_instance_updated'",
            "event_type='prometheus_instance_deleted'",
        ),
        'app/alertmanager/routes.py': (
            "event_type='alertmanager_instance_created'",
            "event_type='alertmanager_instance_updated'",
            "event_type='alertmanager_instance_deleted'",
        ),
    }.items():
        require(path, *tokens)
    require(
        'app/jobs/routes.py',
        "event_type='job_policy_updated'",
        "event_type='job_manual_dispatch'",
        "'job_cancellation_requested'",
        'record_operational_activity(',
    )
    require(
        'app/platform_operations/data_lifecycle/service.py',
        "event_type='data_lifecycle_policy_updated'",
        "event_type='data_lifecycle_execution_requested'",
        'record_operational_activity(',
    )
    require(
        'app/platform_operations/kubernetes/secret_reveal/routes.py',
        "event_type='kubernetes_secret_reveal_cluster_readiness_updated'",
        "event_type='kubernetes_secret_reveal_namespace_policy_updated'",
        'record_operational_activity(',
    )
    require(
        'app/users/routes.py',
        "event_type='user_created'",
        "event_type='user_updated'",
        "event_type='user_deleted'",
        "event_type='identity_provider_created'",
        "event_type='identity_provider_updated'",
    )
    require(
        'app/access/roles/routes.py',
        "event_type='rbac_role_created'",
        "event_type='rbac_role_updated'",
        "event_type='rbac_role_deleted'",
    )
    require(
        'app/settings/routes.py',
        "event_type='account_security'",
        "event_type='user_preference'",
        'OperationalDeliveryPolicy.AUDIT_ONLY',
        'toast_oob=True',
    )
    require(
        'app/notifications/event_catalog.py',
        "'configmap_management': 'ConfigMap Management'",
        "'tls_certificate': 'TLS Certificate'",
        "'secret_management': 'Secret Management'",
        "'integrations': 'Integrations'",
        "'platform_operations': 'Platform Operations'",
        "'access': 'Access'",
        "'settings': 'Settings'",
    )
    require(
        'docs/design/KAORI_OPERATIONAL_FEEDBACK_COVERAGE_V1.md',
        'ConfigMap Management',
        'TLS Certificate',
        'Secret Management',
        'Integrations',
        'Platform Operations',
        'Access',
        'Settings',
    )
    require(
        'docs/design/audits/KAORI_OPERATIONAL_FEEDBACK_COVERAGE_AUDIT_2026_08_08.md',
        'Status: **PASS**',
        'ConfigMap Management',
        'TLS Certificate',
        'Secret Management',
        'Integrations',
        'Platform Operations',
        'Access',
        'Settings',
        'Release Gate',
    )
    print('KAORI Operational Feedback Coverage v1: PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
