from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_binding_validation_worker_imports_canonical_binding_model() -> None:
    tasks = read("app/integrations/validation/tasks.py")
    assert "from app.models.integration import IntegrationBinding" in tasks
    assert "db.session.get(IntegrationBinding, binding_id)" in tasks


def test_observability_validation_polling_is_terminal_aware() -> None:
    poller = read("app/templates/integrations/components/_validation_poller.html")
    state = read("app/integrations/validation/state.py")
    web = read("app/integrations/validation/web.py")
    workspace = read("app/integrations/observability/metrics_source/application/workspace_web.py")

    assert 'hx-trigger="every {{ delay }}"' in poller
    assert "'is_active': False if terminal" in state
    assert "'is_complete': True if terminal" in state
    assert "response.headers['Cache-Control'] = 'no-store, max-age=0'" in web
    assert "response.headers['HX-Trigger'] = '{\"kaori:notifications-changed\":{}}'" in web
    assert "context.update(extra_context)" in workspace


def test_metrics_source_tabs_share_primary_header_typography() -> None:
    shared = read("app/templates/components/connection_validation_header.html")
    config = read("app/templates/integrations/components/_provider_configuration_contract.html")
    validation = read("app/templates/integrations/observability/metrics_source/partials/_detail_validation_content.html")
    runtime = read("app/templates/integrations/observability/metrics_source/partials/_runtime_panel.html")
    scope = read("app/templates/integrations/observability/metrics_source/partials/_detail_scope.html")

    primary_title = "text-base font-semibold text-content-primary"
    primary_description = "mt-1 max-w-3xl text-sm leading-6 text-content-secondary"

    assert primary_title in shared
    assert primary_description in shared
    assert primary_title in config
    assert primary_description in config
    assert primary_title in scope
    assert "max-w-3xl text-sm leading-6 text-content-secondary" in scope
    assert "connection_validation_header.render(" in validation
    assert "connection_validation_header.render(" in runtime
    assert "mt-0.5 max-w-2xl text-xs leading-5 text-content-muted" not in shared

def test_integration_provider_families_share_primary_workspace_typography() -> None:
    shared = read("app/templates/components/connection_validation_header.html")
    configuration = read("app/templates/integrations/components/_provider_configuration_contract.html")
    metrics_scope = read("app/templates/integrations/observability/metrics_source/partials/_detail_scope.html")
    alert_scope = read("app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_scope.html")
    minio_scope = read("app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_scope.html")
    kubernetes_connection = read("app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_connection_contract.html")
    kubernetes_inventory = read("app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_inventory_lifecycle.html")

    primary_title = "text-base font-semibold text-content-primary"
    primary_description = "text-sm leading-6 text-content-secondary"

    for source in (shared, configuration, metrics_scope, alert_scope, minio_scope, kubernetes_connection, kubernetes_inventory):
        assert primary_title in source
        assert primary_description in source

    assert "mt-1 max-w-3xl text-sm leading-6 text-content-secondary" in shared
    assert "mt-1 max-w-3xl text-sm leading-6 text-content-secondary" in configuration
    assert "mt-0.5 max-w-2xl text-xs leading-5 text-content-muted" not in shared



def test_binding_polling_recovers_durable_binding_identity_without_redis_metadata() -> None:
    state = read('app/integrations/validation/state.py')
    metrics_workspace = read(
        'app/integrations/observability/metrics_source/application/workspace_web.py'
    )
    alert_workspace = read(
        'app/integrations/observability/alert_source/providers/alertmanager/application/workspace_web.py'
    )
    metrics_scope = read(
        'app/templates/integrations/observability/metrics_source/partials/_detail_scope.html'
    )
    alert_scope = read(
        'app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_scope.html'
    )

    assert "scope_type') or '') != 'integration_binding'" in state
    assert "prefix = 'binding:'" in state
    assert "payload['binding_id'] = binding_id" in state
    for workspace in (metrics_workspace, alert_workspace):
        assert "snapshot.setdefault('binding_id', binding.id)" in workspace
    for scope in (metrics_scope, alert_scope):
        assert "binding_validation_job.get('binding_id')" in scope
        assert 'binding_poll_active' in scope
        assert 'binding_validation_job.binding_id' not in scope


def test_all_integration_primary_workspaces_follow_one_typography_hierarchy() -> None:
    direct_primary = [
        read('app/templates/integrations/overview.html'),
        read('app/templates/integrations/partials/_domain_workspace.html'),
        read('app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_connection_contract.html'),
        read('app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_inventory_lifecycle.html'),
        read('app/templates/integrations/observability/metrics_source/partials/_detail_scope.html'),
        read('app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_scope.html'),
        read('app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_scope.html'),
        read('app/templates/integrations/observability/metrics_source/instance_form.html'),
        read('app/templates/integrations/observability/alert_source/providers/alertmanager/instance_form.html'),
        read('app/templates/integrations/storage/object_storage/providers/minio/instance_form.html'),
    ]
    shared_header_consumers = [
        read('app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capability_workspace.html'),
        read('app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_runtime_workspace.html'),
        read('app/templates/integrations/observability/metrics_source/partials/_detail_validation_content.html'),
        read('app/templates/integrations/observability/metrics_source/partials/_runtime_panel.html'),
        read('app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_detail_validation_content.html'),
        read('app/templates/integrations/observability/alert_source/providers/alertmanager/partials/_runtime_panel.html'),
        read('app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_validation.html'),
        read('app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_runtime.html'),
    ]

    for source in direct_primary:
        assert 'text-base font-semibold text-content-primary' in source
        assert 'text-sm leading-6 text-content-secondary' in source

    for source in shared_header_consumers:
        assert 'connection_validation_header.render(' in source

    standard = read('docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md')
    assert 'Primary workspace title' in standard
    assert 'Secondary section title' in standard
    assert 'Evidence label / helper' in standard
