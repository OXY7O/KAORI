from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_resource_profiles_use_server_owned_kaori_content_tabs() -> None:
    page = read('app/templates/kubernetes/tenant/resource_profiles.html')
    routes = read('app/kubernetes/tenant/routes.py')

    assert 'components/content_tabs.html' in page
    assert 'content_tabs.render_links' in page
    assert 'id="resource-profile-workspace"' in page
    assert "('profiles', 'Profile Library'" in page
    assert "('capacity', 'Capacity Governance'" in page
    assert "('workflow', 'Workflow Guide'" in page
    assert "hx_target='#resource-profile-workspace'" in page
    assert "hx_select='#resource-profile-workspace'" in page
    assert "active_resource_profile_view" in page

    assert "active_view not in {'profiles', 'capacity', 'workflow'}" in routes
    assert "active_resource_profile_view=active_view" in routes
    assert "view='capacity'" in routes


def test_resource_profile_form_keeps_locked_presets_and_contextual_guidance() -> None:
    form = read('app/templates/kubernetes/tenant/partials/_resource_profile_form.html')
    script = read('app/static/js/tenant_resource_profile_presets.js')

    assert 'Create Resource Profile' in form
    assert 'Identity &amp; Lineage' in form
    assert 'Quota Guardrails' in form
    assert 'Container Defaults' in form
    assert 'Operator rule' in form
    assert 'Custom keeps lineage' in form
    assert 'bg-kaori-soft' in form
    assert 'resource-profile-contract-tip' in form
    assert 'resource-profile-class-tip' in form
    assert 'resource-profile-base-tip' in form
    assert 'data-tenant-profile-class' in form
    assert 'data-tenant-base-preset' in form
    assert 'data-tenant-resource-field="{{ field }}"' in form
    assert 'setReadonly(fields, true)' in script
    assert "classSelect?.value === 'custom'" in script
    assert "document.addEventListener('htmx:afterSwap'" in script


def test_resource_profile_registry_uses_canonical_htmx_filters_and_pagination() -> None:
    registry = read('app/templates/kubernetes/tenant/partials/_resource_profile_registry.html')
    service = read('app/kubernetes/tenant/service.py')

    assert 'components/table_registry.html' in registry
    assert 'registry_ui.filter_form' in registry
    assert 'registry_ui.clear_filters_link' in registry
    assert 'registry_ui.footer' in registry
    assert 'profile_search' in registry
    assert 'profile_class' in registry
    assert 'profile_state' in registry
    assert 'Rows' not in registry
    assert '>Apply<' not in registry
    assert '_pagination_footer.html' not in registry
    assert 'Resource Profile Registry' in registry
    assert 'Requests' in registry
    assert 'Namespace Quota' in registry
    assert 'Container Defaults' in registry
    assert 'Lineage' in registry

    assert 'def get_resource_profile_registry_context(' in service
    assert 'paginate_query(' in service
    assert "'profile_registry_filters':" in service
    assert "'profile_class_filter_options':" in service


def test_resource_profile_workflow_uses_numbered_contract_stages_without_arrow_flow() -> None:
    workflow = read('app/templates/kubernetes/tenant/partials/_resource_profile_workflow.html')
    page = read('app/templates/kubernetes/tenant/resource_profiles.html')

    assert 'Governed Allocation Lifecycle' in workflow
    assert 'Define Contract' in workflow
    assert 'Admit Capacity' in workflow
    assert 'Provision Namespace' in workflow
    assert 'Verify Provider' in workflow
    assert 'Contract Boundaries' in workflow
    assert 'Admission Boundaries' in workflow
    assert 'Open Namespace Provisioning' in workflow
    assert 'operational_flow_steps' not in page


def test_capacity_governance_has_scrollable_cluster_cards_and_policy_reload() -> None:
    capacity = read('app/templates/kubernetes/tenant/partials/_capacity_governance.html')
    page = read('app/templates/kubernetes/tenant/resource_profiles.html')
    script = read('app/static/js/tenant_resource_profile_presets.js')
    service = read('app/kubernetes/tenant/service.py')

    assert 'data-tenant-capacity-policy-form' in capacity
    assert 'data-capacity-policy-cluster' in capacity
    assert 'data-capacity-policy-field=' in capacity
    assert "action_button.classes('primary', full=true)" in capacity
    assert 'overflow-y-auto overscroll-contain' in capacity
    assert 'Budget</span> = allocatable' in capacity
    assert 'Headroom</span> = budget' in capacity
    assert 'active committed namespace' in capacity
    assert 'Quota enforces limits; admission uses committed requests, not physical reservation.' in capacity
    assert 'Unknown evidence never becomes zero.' in capacity

    assert 'tenant-capacity-policy-state' in page
    assert "'capacity_policy_state':" in service
    assert "const policies = readJson('tenant-capacity-policy-state')" in script
    assert 'data-default-value' in script
