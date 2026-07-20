from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_prometheus_registration_side_cards_do_not_stretch_main_form() -> None:
    source = read('app/templates/prometheus/instance_form.html')
    assert 'grid gap-6 xl:grid-cols-12 xl:items-start' in source


def test_capability_technical_probes_use_shared_terminal_component() -> None:
    terminal = read('app/templates/components/terminal_command.html')
    prometheus = read('app/templates/prometheus/partials/_detail_validation_content.html')
    alertmanager = read('app/templates/alertmanager/partials/_detail_validation_content.html')
    assert 'font-mono' in terminal
    assert 'navigator.clipboard' in terminal
    assert 'terminal_command.render' in prometheus
    assert 'terminal_command.render' in alertmanager
    assert 'Technical Probe · Run from CLI' in prometheus
    assert 'Technical Probe · Run from CLI' in alertmanager


def test_alertmanager_validation_scope_oob_does_not_duplicate_feedback() -> None:
    validation = read('app/templates/alertmanager/partials/_detail_validation_content.html')
    scope = read('app/templates/alertmanager/partials/_detail_scope.html')
    assert "{% with scope_oob=true %}" in validation
    assert "{% if not scope_oob|default(false) %}" in scope


def test_runtime_history_is_shared_by_all_three_providers() -> None:
    shared = read('app/templates/integrations/partials/_runtime_history.html')
    for wrapper in (
        'app/templates/prometheus/partials/_runtime_history.html',
        'app/templates/alertmanager/partials/_runtime_history.html',
        'app/templates/integrations/kubernetes/partials/_runtime_history.html',
    ):
        assert "integrations/partials/_runtime_history.html" in read(wrapper)
    for fragment in (
        'Recent Runtime Observations',
        'Rows per page',
        'pagination_ui.navigation_classes(disabled=false)',
        'pagination_ui.navigation_classes(disabled=true)',
        'aria-disabled="true"',
    ):
        assert fragment in shared


def test_kubernetes_registration_requires_test_connection_proof() -> None:
    form = read('app/templates/cluster/partials/_form.html')
    routes = read('app/cluster/routes.py')
    registration = read('app/cluster/registration.py')
    for fragment in (
        'Test Connection',
        'name="connection_test_proof"',
        'x-bind:disabled="!connectionVerified"',
        'x-on:kubernetes-connection-tested.window',
        "url_for('cluster.test_new_cluster_connection')",
        'hx-encoding="multipart/form-data"',
    ):
        assert fragment in form
    for fragment in (
        "@cluster_bp.post('/add/test-connection')",
        'verify_cluster_registration_proof(',
        'test_cluster_draft_connection(',
        "event_type='cluster_connection_test'",
        "event_type='cluster_connection_test_failed'",
        "event_type='cluster_create_rejected'",
    ):
        assert fragment in routes
    assert 'REGISTRATION_PROOF_MAX_AGE_SECONDS = 600' in registration
    assert 'kubeconfig_sha256' in registration


def test_add_and_edit_cluster_use_standard_wide_context_workspace() -> None:
    add = read('app/templates/cluster/add.html')
    edit = read('app/templates/cluster/edit.html')
    header = read('app/templates/cluster/partials/_page_header.html')
    for source in (add, edit):
        assert 'xl:col-span-8' in source
        assert 'xl:col-span-4 xl:sticky xl:top-5' in source
        assert 'Related Operational Workspace' in source
        assert 'Kubernetes RBAC & Access Contract' in source
    assert 'Kubernetes Registration Flow' in add
    assert 'Kubernetes Configuration Flow' in edit
    assert 'page_hero.context_metric' in header
    assert 'Back to Registry' in header


def test_kubernetes_manage_workspace_matches_provider_tab_contract() -> None:
    detail = read('app/templates/integrations/kubernetes/detail.html')
    routes = read('app/integrations/routes.py')
    capability = read('app/templates/integrations/kubernetes/partials/_capability_workspace.html')
    for tab in ('Configuration', 'Validation & Capabilities', 'Runtime & History', 'Inventory & Lifecycle'):
        assert tab in detail
    assert 'rounded-t-xl border px-4 py-2.5 text-sm font-semibold' in detail
    assert 'Review Validation' in detail
    assert 'Back to Registry' in detail
    assert "@integrations_bp.post('/kubernetes/<string:cluster_id>/capabilities/validate')" in routes
    assert "@integrations_bp.get('/kubernetes/<string:cluster_id>/capabilities/validate/status/<string:task_id>')" in routes
    assert 'enqueue_instance_validation(' in routes
    assert 'Run Full Validation' in capability
    assert 'Kubernetes RBAC Verification' in capability
    assert 'Remediation Priority' in capability


def test_kubernetes_registry_uses_compact_icon_actions() -> None:
    registry = read('app/templates/integrations/kubernetes/partials/_registry.html')
    assert 'min-w-[980px] table-fixed' in registry
    assert 'w-[300px]' in registry
    assert 'w-[150px]' in registry
    assert registry.count('inline-flex h-9 w-9') >= 5
    for label in ('Manage', 'Configure', 'Bind Prometheus', 'Bind Alertmanager', 'Delete'):
        assert f'<span class="sr-only">{label}</span>' in registry
    assert '>Manage</a>' not in registry
    assert '>Configure</a>' not in registry


def test_integrations_overview_hero_uses_standard_compact_context_panel() -> None:
    hero = read('app/templates/integrations/partials/_hero.html')
    assert 'font-medium leading-6 text-brand-foreground-muted sm:text-base' in hero
    assert 'page_hero.context_panel_metrics_classes()' in hero
    assert hero.count('page_hero.context_metric') == 2
    assert hero.count('page_hero.primary_action_classes()') == 1
    assert hero.count('page_hero.secondary_action_classes()') == 1
    assert 'Choose a supported provider' not in hero
