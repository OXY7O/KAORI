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
            active_tab='connections',
            connections=[],
            pagination=pagination_payload(build_pagination_window(total_items=0)),
            selected_query='',
            selected_connection_id=None,
            total_connections=0,
            details=None,
            can_jobs=False,
            can_inventory=False,
        )
    assert 'Ansible Connections' in rendered
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
            active_tab='connections',
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
    hero = (ROOT / 'app/templates/infrastructure_automation/_hero.html').read_text()
    workspace = (ROOT / 'app/templates/infrastructure_automation/_lifecycle_workspace.html').read_text()
    assert 'page_hero.context_header(' in hero
    assert 'data-kaori-automation-connection-registry' in workspace
    assert 'data-kaori-automation-lifecycle-posture' in workspace
    assert 'section_intro.render(' in workspace
    assert workspace.index('data-kaori-automation-lifecycle-posture') < workspace.index('data-kaori-remote-review-evidence')
    assert workspace.index('data-kaori-remote-review-evidence') < workspace.index('id="infrastructure-automation-assets"')
    assert 'components/states/_empty_state.html' in workspace
    assert 'Run Kubespray' not in workspace


def test_selected_source_only_connection_renders_lifecycle_only():
    app = create_app('testing')
    connection = SimpleNamespace(id=11, name='Kubespray Fixture', environment='development')
    details = {
        'connection': connection,
        'repository': 'OXY7O/kaori-operations',
        'source_revision': 'a' * 40,
        'source_state': 'not_checked',
        'preflight': {
            'state': 'blocked',
            'review_verified_gates': 0,
            'review_required_gates': 8,
            'governance_verified_gates': 0,
            'governance_required_gates': 2,
            'next_review_requirement': 'Revalidate the exact approved source.',
        },
        'plan': {'state': 'not_generated', 'description': 'No review-only Plan.'},
        'can_inventory': True,
        'assets': {'is_empty': True, 'state': 'blocked'},
        'inventory_store': {'state': 'not_recorded', 'description': 'No provider receipt.', 'fingerprint': None},
        'cluster_bindings': [],
        'can_jobs': True,
        'remote_review': {'tone': 'unknown', 'label': 'Not Recorded', 'description': 'No review receipt.'},
        'jobs': [],
    }
    with app.test_request_context('/platform-operations/infrastructure-automation/'):
        rendered = render_template(
            PARTIAL,
            active_tab='lifecycle',
            connections=[connection],
            pagination=pagination_payload(build_pagination_window(total_items=1)),
            selected_query='',
            selected_connection_id=11,
            total_connections=1,
            details=details,
            can_jobs=True,
            can_inventory=True,
        )
    for label in (
        'Kubespray Fixture',
        'Validation Required',
        '0/8',
        '0/2',
        'Not Generated',
        'Cluster Mutation Not Admitted',
    ):
        assert label in rendered
    assert 'No Ansible Connections' not in rendered
    assert 'Run Kubespray' not in rendered
    assert 'No Registered Hosts' not in rendered
    assert 'No Automation Executions' not in rendered


def test_automation_hero_uses_compact_description_and_three_metadata_items():
    hero = (ROOT / 'app/templates/infrastructure_automation/_hero.html').read_text()
    assert 'Manage governed infrastructure automation.' in hero
    assert hero.count('page_hero.meta_label(') == 3
    assert "page_hero.meta_label('layers-3', '1 Available Profile')" in hero
    assert 'page_hero.metadata_row_classes()' in hero


def test_overview_has_no_connection_selector_or_scoped_details():
    app = create_app('testing')
    with app.test_request_context('/platform-operations/infrastructure-automation/'):
        rendered = render_template(
            PARTIAL,
            active_tab='overview',
            total_connections=2,
            selected_connection_id=None,
            details=None,
            overview={'host_assignments': 6, 'cluster_bindings': 0, 'executions': None},
        )
    assert 'Automation Overview' in rendered
    assert 'Host Assignments' in rendered
    assert 'Restricted' in rendered
    assert 'data-kaori-automation-selected-scope' not in rendered
    assert 'data-kaori-canonical-registry-filter' not in rendered
    assert 'data-kaori-automation-lifecycle-posture' not in rendered
    assert 'data-kaori-tab-variant="integrated-workspace-server"' in rendered


def test_tabs_preserve_scope_and_isolate_inventory_from_execution_history():
    app = create_app('testing')
    connection = SimpleNamespace(id=11, name='Kubespray Fixture', environment='development')
    details = {
        'connection': connection,
        'repository': 'OXY7O/kaori-operations',
        'can_inventory': True,
        'assets': {'is_empty': True, 'state': 'blocked'},
        'inventory_store': {'state': 'not_recorded', 'description': 'No provider receipt.', 'fingerprint': None},
        'cluster_bindings': [],
        'can_jobs': True,
        'jobs': [],
    }
    with app.test_request_context('/platform-operations/infrastructure-automation/'):
        context = dict(total_connections=1, selected_connection_id=11, details=details)
        inventory = render_template(PARTIAL, active_tab='inventory', **context)
        executions = render_template(PARTIAL, active_tab='executions', **context)
    assert 'No Registered Hosts' in inventory
    assert 'No Cluster Associations' in inventory
    assert 'No Automation Executions' not in inventory
    assert 'No Automation Executions' in executions
    assert 'No Registered Hosts' not in executions
    assert 'connection_id=11' in inventory
    assert 'connection_id=11' in executions
    assert 'Change Connection' in inventory


def test_profile_catalog_distinguishes_available_and_planned_workspaces():
    app = create_app('testing')
    with app.test_request_context('/platform-operations/infrastructure-automation/?tab=profiles'):
        rendered = render_template(
            PARTIAL,
            active_tab='profiles',
            total_connections=0,
            selected_connection_id=None,
            details=None,
        )
    for label in ('Kubernetes Lifecycle', 'Linux Hosts', 'Middleware &amp; Database', 'Network Automation'):
        assert label in rendered
    assert rendered.count('Open Workspace') == 1
    assert rendered.count('>Unavailable</span>') == 3
    assert 'data-kaori-automation-selected-scope' not in rendered
    assert 'data-kaori-canonical-registry-filter' not in rendered


def test_automation_overview_reuses_tenant_estate_components():
    template = (ROOT / 'app/templates/infrastructure_automation/_overview.html').read_text()
    assert 'resource_posture_grid.render(estate_metrics, columns=5)' in template
    assert 'operational_section_card.render(' in template
    assert 'Operational Attention & Activity' in template
    assert 'operational_metric_card' not in template
    assert 'workspace_summary_card' not in template


def test_primary_navigation_precedes_hero_and_covers_foundation_surfaces():
    workspace = (ROOT / 'app/templates/infrastructure_automation/_lifecycle_workspace.html').read_text()
    assert workspace.index('workspace_tabs.render_navigation(') < workspace.index('infrastructure_automation/_hero.html')
    for label in ('Overview', 'Hosts & Inventories', 'Profiles', 'Patching', 'Plans',
                  'Runs & Evidence', 'Schedules', 'Compliance'):
        assert label in workspace
    overview = (ROOT / 'app/templates/infrastructure_automation/_overview.html').read_text()
    assert '_profiles.html' not in overview


def test_planned_capabilities_are_read_only_and_do_not_require_a_connection():
    app = create_app('testing')
    with app.test_request_context('/platform-operations/infrastructure-automation/'):
        for tab, label in (('patching', 'Patch Discovery'), ('schedules', 'Scheduled Discovery'),
                           ('compliance', 'Baseline Evaluation')):
            rendered = render_template(PARTIAL, active_tab=tab, total_connections=0,
                                       selected_connection_id=None, details=None)
            assert f'data-kaori-automation-planned="{tab}"' in rendered
            assert label in rendered
            assert 'Planned' in rendered
            assert 'data-kaori-automation-selected-scope' not in rendered
            assert '<form' not in rendered
            assert 'Run Kubespray' not in rendered
