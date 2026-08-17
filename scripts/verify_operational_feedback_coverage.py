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
    # Kubernetes operational CRUD surfaces.
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

    # Provider and integration CRUD/action surfaces.
    for path, tokens in {
        'app/cluster/routes.py': (
            "event_type='cluster_create'",
            "event_type='cluster_update'",
            "event_type='cluster_delete'",
        ),
        'app/metrics_sources/registration_web.py': ("event_type='metrics_source_created'",),
        'app/metrics_sources/routes.py': ("event_type='metrics_source_deleted'",),
        'app/metrics_sources/edit_web.py': ("event_type='metrics_source_updated'",),
        'app/alert_sources/providers/alertmanager/registration_web.py': ("event_type='alertmanager_instance_created'",),
        'app/alert_sources/providers/alertmanager/routes.py': ("event_type='alertmanager_instance_deleted'",),
        'app/alert_sources/providers/alertmanager/edit_web.py': ("event_type='alertmanager_instance_updated'",),
        'app/object_storage/providers/minio/routes.py': (
            "event_type='minio_provider_registered'",
            "event_type='minio_provider_updated'",
            "event_type='minio_instance_deleted'",
        ),
    }.items():
        require(path, *tokens)

    require(
        'app/notification_channels/routes.py',
        "event_type='integration.notification_channel.delete_blocked'",
        "event_type='integration.notification_channel.deleted'",
        "event_type=f'integration.notification_channel.{action}'",
        'queue_feedback=True',
    )

    # Reports: generation, templates, schedules, storage verification, and archive lifecycle.
    require(
        'app/reports/generate/routes.py',
        "event_type='report_generation_queue_failed'",
        "event_type='report_generation_queued'",
        'queue_feedback=True',
    )
    require(
        'app/reports/report_templates/routes.py',
        "event_type='report_template_create'",
        "event_type='report_template_update'",
        "event_type='report_template_delete'",
        "event_type='report_template_duplicate'",
        'queue_feedback=True',
    )
    require(
        'app/reports/schedules/routes.py',
        "event_type='report_schedule_create'",
        "event_type='report_schedule_update'",
        "event_type='report_schedule_toggle'",
        "event_type='report_schedule_delete'",
        "event_type='report_schedule_run'",
        'queue_feedback=True',
    )
    require(
        'app/reports/generated/routes.py',
        "event_type='generated_reports_bulk_archive'",
        "event_type='generated_report_archive'",
        "event_type='generated_report_restore'",
        'queue_feedback=True',
    )
    require(
        'app/reports/storage/routes.py',
        "event_type='report_storage_verification'",
        'queue_feedback=True',
    )

    # Platform Operations and Jobs.
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

    # Access administration and user lifecycle.
    require(
        'app/users/routes.py',
        "event_type='user_created'",
        "event_type='user_updated'",
        "event_type='user_activated'",
        "event_type='user_deactivated'",
        "event_type='user_password_reset'",
        "event_type='user_restored'",
        "event_type='user_deleted'",
        'user_management_feedback(',
    )
    require(
        'app/users/notifications.py',
        'queue_feedback: bool = True',
        'queue_feedback=queue_feedback',
    )
    require(
        'app/identity_providers/routes.py',
        "event_type='identity_provider_created'",
        "event_type='identity_provider_updated'",
        "event_type='identity_provider_validated'",
        "event_type='external_identity_provisioned'",
    )
    require(
        'app/identity_providers/notifications.py',
        'queue_feedback: bool = True',
        'queue_feedback=queue_feedback',
    )
    require(
        'app/access/roles/routes.py',
        "event_type='rbac_role_created'",
        "event_type='rbac_role_updated'",
        "event_type='rbac_role_deleted'",
        'role_access_feedback(',
    )

    # Settings: success/failure actions must both reach the canonical toast stack.
    require(
        'app/settings/general/actions.py',
        "event_type='user_preference'",
        'OperationalDeliveryPolicy.AUDIT_ONLY',
        'create_transient_feedback(',
        'queue_feedback=not is_htmx',
    )
    require(
        'app/settings/account/actions.py',
        "event_type='account_security'",
        'OperationalDeliveryPolicy.AUDIT_ONLY',
        'create_transient_feedback(',
        'queue_feedback=not is_htmx',
        "reason_code='external_credential_owner'",
    )
    require('app/settings/routes.py', 'toast_oob=True')

    # Canonical event/category ownership and documentation.
    require(
        'app/notifications/event_catalog.py',
        "'notifications/event_categories.yaml'",
        'CATEGORY_LABELS =',
        'CATEGORY_ICONS =',
        'event_category_key(',
    )
    require(
        'app/definitions/catalogs/notifications/event_categories.yaml',
        'configmap_management:',
        'label: ConfigMap Management',
        'label: TLS Certificate',
        'label: Secret Management',
        'label: Integrations',
        'label: Platform Operations',
        'label: Access',
        'label: Settings',
        'prefixes:',
        'metrics_source_',
    )
    require(
        'docs/design/KAORI_OPERATIONAL_FEEDBACK_COVERAGE_V1.md',
        'ConfigMap Management',
        'TLS Certificate',
        'Secret Management',
        'Integrations',
        'Reports',
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
        'Reports',
        'Platform Operations',
        'Access',
        'Settings',
        'Release Gate',
    )

    print('KAORI Operational Feedback Coverage v1.1: PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
