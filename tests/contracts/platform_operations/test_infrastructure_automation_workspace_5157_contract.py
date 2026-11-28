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
    operations = next(item for section in sections for item in section['items'] if item['key'] == 'operations_center')
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
    assert 'Setup Required' in rendered
    assert 'Register Connection' in rendered
    assert 'data-kaori-empty-state' in rendered
    assert 'Cluster Mutation Not Admitted' not in rendered
    assert 'data-kaori-infrastructure-automation-detail' not in rendered
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
    assert 'integration_type=INTEGRATION_TYPE' in workspace
    assert 'integration_instance_id=selected.id' in workspace
    assert "asset_type='kubernetes_cluster'" in workspace
    assert "'execution_authorized': False" in workspace
    assert "@permission_required('integrations.manage')" in route
    assert '@bp.get(' in route
    assert '@bp.post(' not in route


def test_workspace_does_not_trust_unbounded_or_unqualified_input():
    from app.infrastructure_automation.workspace import _bounded_query

    assert _bounded_query('  kubespray  ') == 'kubespray'
    assert _bounded_query('a' * 150) == 'a' * 80


def test_provider_inventory_evidence_is_permission_scoped_and_non_executable():
    workspace = (ROOT / 'app/infrastructure_automation/workspace.py').read_text()
    projection = (ROOT / 'app/infrastructure_automation/kubernetes/inventory_receipt.py').read_text()
    template = (ROOT / 'app/templates/infrastructure_automation/_lifecycle_workspace.html').read_text()
    assert "'inventory_store': committed_inventory_receipt_review(selected).presentation() if can_inventory else None" in workspace
    assert 'data-kaori-inventory-store-evidence' in template
    assert '{% if not details.can_inventory %}' in template
    assert 'Historical Source Aligned' in template
    assert 'Run Kubespray' not in template
    assert "'execution_authorized': False" not in projection or 'execution_authorized: bool = False' in projection
    for prohibited in ('requests.get(', 'ansible_runner.run', 'subprocess.run(', 'secret_id.data'):
        assert prohibited not in projection
    assert 'defer(OpenBaoInstance.secret_id)' in projection
    assert 'defer(VaultInstance.secret_id)' in projection


def test_remote_review_posture_is_jobs_permission_scoped_and_non_authorizing():
    workspace = (ROOT / 'app/infrastructure_automation/workspace.py').read_text()
    projection = (ROOT / 'app/infrastructure_automation/remote_review_posture.py').read_text()
    template = (ROOT / 'app/templates/infrastructure_automation/_lifecycle_workspace.html').read_text()
    assert "'remote_review': committed_remote_review_posture(selected).presentation() if can_jobs else None" in workspace
    assert '{% if details.can_jobs and details.remote_review %}' in template
    assert 'data-kaori-remote-review-evidence' in template
    assert 'Historical Review' in projection
    assert 'execution_authorized: bool = False' in projection
    assert '.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).first()' in projection
    for prohibited in ('ansible_runner.run', '.apply_async(', 'review_remote_preflight_target(', 'resolve_remote_worker_review('):
        assert prohibited not in projection


def test_filtered_connections_are_not_initial_setup():
    app = create_app('testing')
    with app.test_request_context('/platform-operations/infrastructure-automation/?q=missing'):
        rendered = render_template(
            PARTIAL,
            connections=[],
            pagination=pagination_payload(build_pagination_window(total_items=0)),
            selected_query='missing',
            selected_connection_id=None,
            total_connections=2,
            details=None,
            can_jobs=False,
            can_inventory=False,
        )
    assert 'No Matching Connections' in rendered
    assert 'No Results' in rendered
    assert 'Clear Filters' in rendered
    assert 'No Ansible Connections' not in rendered
    assert 'Cluster Mutation Not Admitted' not in rendered


def test_lifecycle_workspace_uses_shared_hero_and_separate_operational_sections():
    hero = (ROOT / 'app/templates/infrastructure_automation/index.html').read_text()
    workspace = (ROOT / 'app/templates/infrastructure_automation/_lifecycle_workspace.html').read_text()
    assert 'page_hero.context_card(' in hero
    assert 'data-kaori-automation-connection-registry' in workspace
    assert 'data-kaori-automation-lifecycle-posture' in workspace
    assert 'section_intro.render(' in workspace
    assert workspace.index('data-kaori-automation-lifecycle-posture') < workspace.index('data-kaori-remote-review-evidence')
    assert workspace.index('data-kaori-remote-review-evidence') < workspace.index('id="infrastructure-automation-assets"')
    assert 'components/states/_empty_state.html' in workspace
    assert 'Run Kubespray' not in workspace
