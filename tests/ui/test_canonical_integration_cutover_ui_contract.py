from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / 'app/templates'


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_provider_workspaces_use_the_canonical_hero_and_context_panel() -> None:
    for relative_path in (
        'app/templates/integrations/kubernetes.html',
        'app/templates/integrations/prometheus.html',
        'app/templates/integrations/alertmanager.html',
        'app/templates/prometheus/instance_form.html',
        'app/templates/prometheus/instance_detail.html',
        'app/templates/alertmanager/instance_form.html',
        'app/templates/alertmanager/instance_detail.html',
    ):
        source = read(relative_path)
        assert 'page_hero.shell_classes()' in source, relative_path
        assert 'page_hero.context_panel_classes()' in source, relative_path
        assert 'bg-gradient-to-r' not in source, relative_path


def test_provider_registries_keep_headers_and_shared_empty_states() -> None:
    registries = (
        'app/templates/integrations/kubernetes/partials/_registry.html',
        'app/templates/integrations/prometheus/partials/_inventory_content.html',
        'app/templates/integrations/alertmanager/partials/_inventory_content.html',
    )
    for relative_path in registries:
        source = read(relative_path)
        assert '<table' in source and '<thead' in source and '<tbody' in source, relative_path
        assert "components/states/_empty_state.html" in source, relative_path
        assert 'text-right' in source, relative_path

    assert 'Showing 0–0 of 0 connections' not in read(
        'app/templates/integrations/alertmanager/partials/_inventory_content.html'
    )


def test_provider_forms_use_shared_action_validation_and_guidance_components() -> None:
    for relative_path in (
        'app/templates/prometheus/instance_form.html',
        'app/templates/alertmanager/instance_form.html',
    ):
        source = read(relative_path)
        assert 'components/form_action_bar.html' in source, relative_path
        assert 'components/connection_validation_header.html' in source, relative_path
        assert 'info_flow.render(' in source, relative_path
        assert 'related_page_card.render(' in source, relative_path
        assert 'context_guidance_card.render(' in source, relative_path
        assert 'components/operation_feedback_oob.html' in source, relative_path


def test_provider_validation_and_binding_posture_are_shared() -> None:
    for relative_path in (
        'app/templates/prometheus/partials/_detail_validation_content.html',
        'app/templates/alertmanager/partials/_detail_validation_content.html',
        'app/templates/integrations/kubernetes/partials/_capability_workspace.html',
    ):
        source = read(relative_path)
        assert 'components/connection_validation_header.html' in source, relative_path
        assert 'components/operation_feedback_oob.html' in source, relative_path

    for relative_path in (
        'app/templates/prometheus/partials/_detail_scope.html',
        'app/templates/alertmanager/partials/_detail_scope.html',
    ):
        source = read(relative_path)
        assert "integrations/partials/_binding_readiness.html" in source, relative_path
        assert 'Dedicated source identity' in source, relative_path
        assert 'Legacy unscoped binding' not in source, relative_path


def test_binding_routes_have_one_canonical_owner() -> None:
    routes = read('app/integrations/routes.py')
    registry = read('app/templates/integrations/kubernetes/partials/_registry.html')

    assert "@integrations_bp.route('/prometheus/bind', methods=['GET', 'POST'])" in routes
    assert "@integrations_bp.route('/alertmanager/bind', methods=['GET', 'POST'])" in routes
    assert "url_for('integrations.bind_prometheus_source'" not in registry
    assert "url_for('integrations.bind_alertmanager_source'" not in registry
    assert "url_for('integrations.kubernetes_detail', cluster_id=row.cluster_id)" in registry


def test_retired_provider_templates_and_page_local_state_components_are_absent() -> None:
    retired = (
        'app/templates/prometheus/config.html',
        'app/templates/prometheus/instances.html',
        'app/templates/alertmanager/config.html',
        'app/templates/alertmanager/instances.html',
        'app/templates/components/page_context_card.html',
        'docs/design/components/PAGE_CONTEXT_CARD.md',
        'app/templates/analytics/overview/partials/_empty_state.html',
    )
    for relative_path in retired:
        assert not (ROOT / relative_path).exists(), relative_path


def test_sidebar_state_uses_only_the_canonical_storage_key() -> None:
    source = read('app/templates/layouts/app.html')
    assert "localStorage.getItem('kaori.sidebarExpanded')" in source
    assert "localStorage.setItem('kaori.sidebarExpanded'" in source
    assert 'kaori.sidebarOpen' not in source


def test_runtime_capability_labels_are_presented_in_python() -> None:
    presentation = read('app/integrations/runtime/presentation.py')
    template = read('app/templates/integrations/partials/_runtime_history.html')

    assert "{'key': capability, 'label': present_key_label(capability)}" in presentation
    assert '{{ capability.label }}' in template
    assert "capability|replace('_', ' ')|title" not in template


def test_alertmanager_mutations_use_the_domain_activity_boundary() -> None:
    source = read('app/alertmanager/routes.py')
    tree = ast.parse(source)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for name in (
        'new_instance',
        'test_new_instance_connection',
        'instance_detail',
        'refresh_runtime',
        'validate_instance',
        'create_binding',
        'remove_binding',
        'delete_instance',
    ):
        assert name in functions
        function_source = ast.get_source_segment(source, functions[name]) or ''
        assert 'record_instance_activity(' in function_source, name


def test_human_readable_filter_labels_follow_title_case() -> None:
    alertmanager = read('app/templates/integrations/alertmanager/partials/_inventory_card.html')
    prometheus = read('app/templates/integrations/prometheus/partials/_instance_inventory.html')
    kubernetes = read('app/templates/integrations/kubernetes/partials/_registry.html')

    assert '>Search Connection</label>' in alertmanager
    assert 'Search Connection' in prometheus
    assert 'Kubernetes Connection Registry' in kubernetes


def test_design_docs_register_the_current_sidebar_and_feedback_contracts() -> None:
    design = read('docs/design/DESIGN_SYSTEM.md')
    sidebar = ROOT / 'docs/design/components/SIDEBAR_NAVIGATION.md'
    feedback = ROOT / 'docs/design/components/OPERATIONAL_ACTION_FEEDBACK.md'

    assert sidebar.exists()
    assert feedback.exists()
    assert 'SIDEBAR_NAVIGATION.md' in design
    assert 'OPERATIONAL_ACTION_FEEDBACK.md' in design
