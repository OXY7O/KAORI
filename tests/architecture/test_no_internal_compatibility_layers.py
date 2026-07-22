from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'app'


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_retired_internal_modules_and_template_wrappers_are_absent() -> None:
    retired = (
        'app/integrations/runtime/contracts.py',
        'app/integrations/deprecations.py',
        'app/prometheus/binding_contract.py',
        'app/reports/storage/base.py',
        'app/analytics/common/dependencies.py',
        'app/analytics/alerts/query_contracts.py',
        'app/inventory/service.py',
        'app/inventory/collector.py',
        'app/templates/prometheus/partials/_runtime_history.html',
        'app/templates/alertmanager/partials/_runtime_history.html',
        'app/templates/integrations/kubernetes/partials/_runtime_history.html',
        'app/templates/cluster/index.html',
        'app/templates/cluster/partials/_table.html',
        'app/templates/cluster/partials/_pagination.html',
        'app/templates/governance/tls_certificates/bulk_update.html',
        'app/templates/governance/tls_certificates/partials/_bulk_feedback.html',
        'app/templates/governance/tls_certificates/partials/_bulk_filters.html',
        'app/templates/governance/tls_certificates/partials/_bulk_target_table.html',
        'app/templates/governance/tls_certificates/partials/_bulk_target_workspace.html',
        'app/templates/governance/tls_certificates/partials/_update_preview.html',
        'app/templates/governance/tls_certificates/partials/_operation_feedback_oob.html',
        'app/templates/components/page_context_card.html',
        'docs/design/components/PAGE_CONTEXT_CARD.md',
        'app/templates/analytics/overview/partials/_empty_state.html',
        'app/analytics/alerts/queries.py',
        'app/analytics/capacity/queries.py',
        'app/analytics/forecast/queries.py',
        'app/analytics/overview/queries.py',
        'app/analytics/storage/queries.py',
        'app/analytics/top_consumers/queries.py',
        'app/analytics/utilization/queries.py',
        'app/analytics/workload/queries.py',
    )
    for relative_path in retired:
        assert not (ROOT / relative_path).exists(), relative_path


def test_internal_compatibility_tokens_do_not_exist_in_active_python() -> None:
    forbidden = (
        'legacy_unscoped',
        'legacy-local',
        'REPORT_STORAGE_ROOT_DIR',
        'materialize_legacy_cluster_config',
        'RECOMMENDATION_CATALOG',
        'can_mutate_target',
        'AlertmanagerConnectionSource',
        'ValidatableAlertmanager',
        'AlertmanagerStatusSource',
        'ReadableAlertmanager',
        'CAPABILITY_DEFINITIONS',
        'ENVIRONMENT_CHOICES',
        'REVEAL_POLICIES',
        '_optional_endpoint_url',
        'legacy_source',
        'details_reported',
        "kaori.sidebarOpen",
        'compatibility window',
        'Old/migrated configurations',
        'Redis remains a compatibility fallback',
        'Redis is a compatibility lock during the JobExecution cutover',
    )
    violations: list[str] = []
    for path in APP.rglob('*.py'):
        source = path.read_text(encoding='utf-8')
        for token in forbidden:
            if token in source:
                violations.append(f'{path.relative_to(ROOT)}: {token}')
    assert not violations, '\n'.join(violations)


def test_retired_product_names_do_not_exist_in_active_application() -> None:
    forbidden = ('kubereport', 'kubreport', 'serverreport', 'hcireport', 'opsin')
    violations: list[str] = []
    for path in APP.rglob('*'):
        if not path.is_file() or path.suffix not in {'.py', '.html', '.js', '.css'}:
            continue
        source = path.read_text(encoding='utf-8', errors='ignore').lower()
        for token in forbidden:
            if token in source:
                violations.append(f'{path.relative_to(ROOT)}: {token}')
    assert not violations, '\n'.join(violations)


def test_registry_requires_operation_adapter_without_dispatch_fallback() -> None:
    registry = read('app/integrations/registry.py')

    assert 'adapter: OperationAdapter' in registry
    assert 'return self.adapter.execute(operation, instance, **kwargs)' in registry
    assert "getattr(self.adapter, 'execute'" not in registry
    assert "if operation == 'runtime.validate'" not in registry
    assert "if operation == 'runtime.health'" not in registry
    assert "if operation == 'runtime.state'" not in registry


def test_provider_package_initializers_register_only() -> None:
    for provider in ('kubernetes', 'prometheus', 'alertmanager'):
        source = read(f'app/integrations/{provider}/__init__.py')
        assert 'registry.register(integration_module)' in source
        assert '__all__' not in source

    kubernetes = read('app/integrations/kubernetes/__init__.py')
    assert 'from app.integrations.kubernetes.resolver import' not in kubernetes


def test_package_initializers_do_not_restore_removed_export_facades() -> None:
    for relative_path in (
        'app/integrations/__init__.py',
        'app/integrations/runtime/__init__.py',
        'app/reports/storage/__init__.py',
        'app/inventory/collectors/__init__.py',
        'app/integrations/validation/__init__.py',
        'app/rbac/__init__.py',
        'app/retention/__init__.py',
        'app/security/__init__.py',
        'app/storage/__init__.py',
        'app/governance/__init__.py',
        'app/users/__init__.py',
        'app/integrations/consumer/__init__.py',
        'app/integrations/alertmanager/normalizers/__init__.py',
        'app/auth/providers/__init__.py',
        'app/inventory/topology/__init__.py',
        'app/users/providers/__init__.py',
        'app/settings/secret_reveal/__init__.py',
        'app/settings/data_lifecycle/__init__.py',
    ):
        tree = ast.parse(read(relative_path))
        executable = [
            node
            for node in tree.body
            if not (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            )
        ]
        assert executable == [], relative_path


def test_credentials_and_report_storage_reject_pre_cutover_formats() -> None:
    credentials = read('app/security/credentials.py')
    report_storage = read('app/reports/storage/service.py')

    assert "if not value.startswith(_PREFIX):\n        raise CredentialEncryptionError(" in credentials
    assert "current = configured or fallback" not in credentials
    assert "current_app.config.get('SECRET_KEY')" not in credentials
    assert "os.getenv('SECRET_KEY')" not in credentials
    assert "INTEGRATION_CREDENTIAL_KEY is required for integration credentials." in credentials
    assert "if ':' not in stored_path:" in report_storage
    assert "Report storage URI must use the local:<object_key> or s3:<object_key> format." in report_storage
    assert 'legacy-local' not in report_storage


def test_retired_bookmark_routes_are_not_registered() -> None:
    prometheus = read('app/prometheus/routes.py')
    alertmanager = read('app/alertmanager/routes.py')
    cluster = read('app/cluster/routes.py')
    reports = read('app/reports/routes.py')
    analytics = read('app/analytics/routes.py')
    intelligence = read('app/intelligence/routes.py')

    assert "@prometheus_bp.get('/instances')" not in prometheus
    assert "'/instances/<int:instance_id>/edit'" not in prometheus
    assert "'/cluster/<string:cluster_id>'" not in alertmanager
    assert "@cluster_bp.get('/')" not in cluster
    assert "'/report-templates'" not in reports
    assert "'/artifacts'" not in reports
    assert "'/anomalies'" not in analytics
    assert "'/rule-catalog'" not in intelligence
    governance = read('app/governance/routes.py')
    assert "'/tls-certificates/<int:certificate_id>/update/preview'" not in governance
    assert "'/tls-certificates/<int:certificate_id>/update/apply'" not in governance
    assert "'/tls-certificates/bulk-update'" not in governance


def test_runtime_compatibility_support_is_explicit_product_behavior() -> None:
    kubernetes = read('app/integrations/kubernetes/compatibility.py')
    alertmanager = read('app/integrations/alertmanager/profiles/alertmanager_v025.py')

    assert "ApiCandidate('batch', 'v1beta1', 'cronjobs', 'legacy')" in kubernetes
    assert "support_level='legacy'" in alertmanager
    assert 'compatibility' in kubernetes.lower()


def test_provider_resolvers_fail_closed_until_validation_evidence_exists() -> None:
    for relative_path in ('app/prometheus/resolver.py', 'app/alertmanager/resolver.py'):
        source = read(relative_path)
        assert "capability_state = 'validation_required'" in source
        assert 'capability_eligible = False' in source or 'technical_eligible = False' in source
        assert "_ELIGIBLE_BINDING_VALIDATION: Final[set[str]] = {'ready'}" in source
        assert "readiness in (_READY_READINESS | _DEGRADED_READINESS)" in source
        assert 'compatibility window' not in source.lower()


def test_prometheus_consumer_requires_recorded_capability_evidence() -> None:
    source = read('app/prometheus/consumer.py')
    assert 'if status is None and not capability_data:' not in source
    assert 'missing.append(capability)' in source
    assert 'readiness remains the compatibility gate' not in source.lower()


def test_job_execution_is_the_only_active_validation_read_authority() -> None:
    source = read('app/integrations/validation/state.py')
    function = source[source.index('def get_active_validation_task_id('):source.index('def release_validation_job(')]
    assert 'from app.jobs.service import find_active_job' in function
    assert '_redis_client()' not in function
    assert 'AsyncResult' not in function
    assert 'except Exception' not in function


def test_analytics_services_bind_directly_to_versioned_query_catalog() -> None:
    for domain in (
        'capacity',
        'forecast',
        'storage',
        'top_consumers',
        'utilization',
        'workload',
    ):
        source = read(f'app/analytics/{domain}/service.py')
        assert 'from app.integrations.prometheus.query_profiles import get_query_expression' in source
        assert f'from app.analytics.{domain} import queries' not in source
        tree = ast.parse(source)
        assert not any(
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == 'queries'
            for node in ast.walk(tree)
        )
        assert f"get_query_expression('analytics.{domain}.queries." in source
