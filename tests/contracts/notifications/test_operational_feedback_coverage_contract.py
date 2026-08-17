from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_feedback_coverage_matrix_is_documented_and_release_gated() -> None:
    matrix = read('docs/design/KAORI_OPERATIONAL_FEEDBACK_COVERAGE_V1.md')
    for category in (
        'ConfigMap Management',
        'TLS Certificate',
        'Secret Management',
        'Integrations',
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
        'Platform Operations',
        'Access',
        'Settings',
    ):
        assert category in audit
    assert 'verify_operational_feedback_coverage.py' in read('scripts/quality_gate.sh')


def test_configmap_and_secret_crud_use_canonical_operational_feedback() -> None:
    configmaps = read('app/kubernetes_operations/configmaps/routes.py')
    secret_support = read('app/kubernetes_operations/secrets/route_support.py')
    secret_crud = read('app/kubernetes_operations/secrets/crud_routes.py')

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
        'app/kubernetes_operations/secrets/tls_routes.py': (
            'kubernetes_tls_secret_rotation',
            'kubernetes_tls_secret_bulk_rotation',
        ),
        'app/governance/tls_certificates/routes.py': ('governance_tls_secret_sync_dispatch',),
        'app/cluster/routes.py': ('cluster_create', 'cluster_update', 'cluster_delete'),
        'app/metrics_sources/registration_web.py': ('metrics_source_created',),
        'app/metrics_sources/routes.py': ('metrics_source_deleted',),
        'app/metrics_sources/edit_web.py': ('metrics_source_updated',),
        'app/alert_sources/providers/alertmanager/registration_web.py': ('alertmanager_instance_created',),
        'app/alert_sources/providers/alertmanager/routes.py': ('alertmanager_instance_deleted',),
        'app/alert_sources/providers/alertmanager/edit_web.py': ('alertmanager_instance_updated',),
        'app/jobs/routes.py': ('job_policy_updated', 'job_manual_dispatch', 'job_cancellation_requested'),
        'app/platform_operations/data_lifecycle/service.py': (
            'data_lifecycle_policy_updated',
            'data_lifecycle_execution_requested',
        ),
        'app/platform_operations/kubernetes/secret_reveal/routes.py': (
            'kubernetes_secret_reveal_cluster_readiness_updated',
            'kubernetes_secret_reveal_namespace_policy_updated',
        ),
        'app/users/routes.py': (
            'user_created',
            'user_updated',
            'user_deleted',
        ),
        'app/identity_providers/routes.py': (
            'identity_provider_created',
            'identity_provider_updated',
            'identity_provider_validated',
        ),
        'app/access/roles/routes.py': ('rbac_role_created', 'rbac_role_updated', 'rbac_role_deleted'),
        'app/settings/routes.py': ('account_security', 'user_preference'),
    }
    for path, events in sources.items():
        text = read(path)
        for event in events:
            assert event in text


def test_general_settings_preference_save_has_toast_and_audit_without_inbox_noise() -> None:
    settings = read('app/settings/routes.py')
    assert 'OperationalDeliveryPolicy.AUDIT_ONLY' in settings
    assert "queue_feedback=not bool(request.headers.get('HX-Request'))" in settings
    assert 'toast_oob=True' in settings
    assert "notification_changed = bool(operation_feedback.get('notification_deck_visible'))" in settings
    assert 'general_settings_saved = True' in settings
