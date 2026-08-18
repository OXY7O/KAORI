from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_feedback_coverage_matrix_is_documented_and_release_gated() -> None:
    matrix = read('docs/design/KAORI_OPERATIONAL_FEEDBACK_COVERAGE_V1.md')
    for category in (
        'ConfigMap Management',
        'TLS Certificate',
        'Secret Management',
        'Integrations',
        'Reports',
        'Platform Operations',
        'Access',
        'Settings',
    ):
        assert category in matrix
    audit = read('docs/design/audits/KAORI_OPERATIONAL_FEEDBACK_COVERAGE_AUDIT_2026_08_08.md')
    assert 'Status: **PASS**' in audit
    for category in (
        'ConfigMap Management',
        'TLS Certificate',
        'Secret Management',
        'Integrations',
        'Reports',
        'Platform Operations',
        'Access',
        'Settings',
    ):
        assert category in audit
    assert 'verify_operational_feedback_coverage.py' in read('scripts/quality_gate.sh')


def test_configmap_and_secret_crud_use_canonical_operational_feedback() -> None:
    configmaps = read('app/kubernetes/operations/configmaps/routes.py')
    secret_support = read('app/kubernetes/operations/secrets/route_support.py')
    secret_crud = read('app/kubernetes/operations/secrets/crud_routes.py')

    for event in ('kubernetes_configmap_created', 'kubernetes_configmap_updated', 'kubernetes_configmap_deleted'):
        assert event in configmaps
    assert 'OperationalDeliveryPolicy.DECK_ON_FAILURE' in configmaps
    assert 'OperationalDeliveryPolicy.PERSISTENT' in configmaps

    for event in ('kubernetes_secret_created', 'kubernetes_secret_data_replaced', 'kubernetes_secret_deleted'):
        assert event in secret_crud
    assert 'OperationalDeliveryPolicy.DECK_ON_FAILURE' in secret_support
    assert 'OperationalDeliveryPolicy.PERSISTENT' in secret_support
    assert "event_type == 'kubernetes_secret_revealed'" in secret_support


def test_tls_integrations_platform_operations_access_and_settings_are_covered() -> None:
    sources = {
        'app/kubernetes/operations/secrets/tls_routes.py': (
            'kubernetes_tls_secret_rotation',
            'kubernetes_tls_secret_bulk_rotation',
        ),
        'app/kubernetes/governance/tls_certificates/routes.py': ('governance_tls_secret_sync_dispatch',),
        'app/kubernetes/cluster/routes.py': ('cluster_create', 'cluster_update', 'cluster_delete'),
        'app/integrations/observability/metrics_source/application/registration_web.py': ('metrics_source_created',),
        'app/integrations/observability/metrics_source/application/routes.py': ('metrics_source_deleted',),
        'app/integrations/observability/metrics_source/application/edit_web.py': ('metrics_source_updated',),
        'app/integrations/observability/alert_source/providers/alertmanager/application/registration_web.py': (
            'alertmanager_instance_created',
        ),
        'app/integrations/observability/alert_source/providers/alertmanager/application/routes.py': (
            'alertmanager_instance_deleted',
        ),
        'app/integrations/observability/alert_source/providers/alertmanager/application/edit_web.py': (
            'alertmanager_instance_updated',
        ),
        'app/platform_operations/jobs/routes.py': (
            'job_policy_updated',
            'job_manual_dispatch',
            'job_cancellation_requested',
        ),
        'app/platform_operations/data_lifecycle/service.py': (
            'data_lifecycle_policy_updated',
            'data_lifecycle_execution_requested',
        ),
        'app/platform_operations/kubernetes/secret_reveal/routes.py': (
            'kubernetes_secret_reveal_cluster_readiness_updated',
            'kubernetes_secret_reveal_namespace_policy_updated',
        ),
        'app/access/users/routes.py': (
            'user_created',
            'user_updated',
            'user_deleted',
        ),
        'app/access/identity_providers/routes.py': (
            'identity_provider_created',
            'identity_provider_updated',
            'identity_provider_validated',
        ),
        'app/access/roles/routes.py': ('rbac_role_created', 'rbac_role_updated', 'rbac_role_deleted'),
        'app/settings/general/actions.py': ('user_preference',),
        'app/settings/account/actions.py': ('account_security',),
    }
    for path, events in sources.items():
        text = read(path)
        for event in events:
            assert event in text


def test_general_settings_preference_save_has_toast_and_audit_without_inbox_noise() -> None:
    actions = read('app/settings/general/actions.py')
    routes = read('app/settings/routes.py')
    assert 'OperationalDeliveryPolicy.AUDIT_ONLY' in actions
    assert 'queue_feedback=not is_htmx' in actions
    assert 'toast_oob=True' in routes
    assert 'notification_changed = result.notification_changed' in routes
    assert 'general_settings_saved = result.saved' in routes


def test_notification_channel_crud_and_settings_failures_reach_canonical_toast_stack() -> None:
    channels = read('app/integrations/delivery/notification_channels/routes.py')
    settings = read('app/settings/account/actions.py')

    assert "event_type=f'integration.notification_channel.{action}'" in channels
    assert "event_type='integration.notification_channel.delete_blocked'" in channels
    assert 'queue_feedback=True' in channels

    assert 'create_transient_feedback(' in settings
    assert 'queue_feedback=not is_htmx' in settings
    assert "reason_code='external_credential_owner'" in settings


def test_reports_mutation_surfaces_use_canonical_operational_feedback() -> None:
    sources = {
        'app/reports/generate/routes.py': ('report_generation_queue_failed', 'report_generation_queued'),
        'app/reports/report_templates/routes.py': (
            'report_template_create',
            'report_template_update',
            'report_template_delete',
            'report_template_duplicate',
        ),
        'app/reports/schedules/routes.py': (
            'report_schedule_create',
            'report_schedule_update',
            'report_schedule_toggle',
            'report_schedule_delete',
            'report_schedule_run',
        ),
        'app/reports/generated/routes.py': (
            'generated_reports_bulk_archive',
            'generated_report_archive',
            'generated_report_restore',
        ),
        'app/reports/storage/routes.py': ('report_storage_verification',),
    }
    for path, events in sources.items():
        source = read(path)
        assert 'queue_feedback=True' in source
        for event in events:
            assert event in source
