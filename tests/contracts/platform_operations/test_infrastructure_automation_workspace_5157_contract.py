"""#5157: read-only Infrastructure Automation workspace and canonical navigation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from flask import render_template

from app import create_app
from app.common.pagination import build_pagination_window, pagination_payload
from app.common.workspace_navigation import build_sidebar_navigation

ROOT = Path(__file__).resolve().parents[3]
PARTIAL = 'infrastructure_automation/_lifecycle_workspace.html'


def _principal():
    return SimpleNamespace(
        is_authenticated=True,
        has_permission=lambda permission: permission in {'integrations.manage', 'jobs.view'},
    )


def test_automation_workspace_is_an_operations_center_capability():
    app = create_app('testing')
    endpoints = {rule.endpoint: rule for rule in app.url_map.iter_rules()}
    endpoint = 'platform_operations.infrastructure_automation.index'
    assert endpoint in endpoints
    rule = endpoints[endpoint]
    assert rule.rule == '/platform-operations/infrastructure-automation/'
    assert 'GET' in rule.methods
    assert 'POST' not in rule.methods

    with app.test_request_context(rule.rule):
        sections = build_sidebar_navigation(endpoint, _principal())
    operations = next(
        item
        for section in sections
        for item in section['items']
        if item['key'] == 'operations_center'
    )
    assert operations['active']
    assert any(
        capability['key'] == 'infrastructure_automation' and capability['active']
        for capability in operations['children']
    )


def test_workspace_empty_state_renders_canonical_ui_without_provision_actions():
    app = create_app('testing')
    with app.test_request_context('/platform-operations/infrastructure-automation/'):
        rendered = render_template(
            PARTIAL,
            connections=[],
            pagination=pagination_payload(build_pagination_window(total_items=0)),
            selected_query='',
            selected_connection_id=None,
            total_connections=0,
            details=None,
            can_jobs=False,
            can_inventory=False,
        )
    assert 'Kubernetes Lifecycle' in rendered
    assert 'No Ansible Connections' in rendered
    assert 'data-kaori-canonical-registry-filter' in rendered
    assert 'data-kaori-canonical-registry-footer' in rendered
    assert 'data-kaori-info-tip-variant="guide"' in rendered
    assert 'Cluster Mutation Not Admitted' in rendered
    assert 'name="per_page"' in rendered
    assert 'value="5"' in rendered
    assert '<form method="POST"' not in rendered
    assert 'Run Kubespray' not in rendered


def test_domain_read_model_preserves_provider_boundary_and_execution_denial():
    workspace = (ROOT / 'app/infrastructure_automation/workspace.py').read_text()
    route = (ROOT / 'app/infrastructure_automation/routes.py').read_text()
    for prohibited in ('ansible_runner.run', 'subprocess.run(', 'requests.get(', '.apply_async('):
        assert prohibited not in workspace
        assert prohibited not in route
    assert "integration_type=INTEGRATION_TYPE" in workspace
    assert "integration_instance_id=selected.id" in workspace
    assert "asset_type='kubernetes_cluster'" in workspace
    assert "'execution_authorized': False" in workspace
    assert "@permission_required('integrations.manage')" in route
    assert '@bp.get(' in route
    assert '@bp.post(' not in route


def test_workspace_does_not_trust_unbounded_or_unqualified_input():
    from app.infrastructure_automation.workspace import _bounded_query

    assert _bounded_query('  kubespray  ') == 'kubespray'
    assert _bounded_query('a' * 150) == 'a' * 80
