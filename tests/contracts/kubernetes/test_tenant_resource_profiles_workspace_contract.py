from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_resource_profiles_use_server_owned_kaori_content_tabs_and_snapshot_stats() -> None:
    page = read('app/templates/kubernetes/tenant/resource_profiles.html')
    routes = read('app/kubernetes/tenant/routes.py')
    service = read('app/kubernetes/tenant/service.py')

    assert 'Resource Profile Snapshot' in page
    assert 'Total Profiles' in page
    assert 'Enabled' in page
    assert 'Custom' in page
    assert 'Active Allocations' in page
    assert 'resource_profile_stats.total' in page
    assert "'resource_profile_stats':" in service

    assert 'components/content_tabs.html' in page
    assert 'content_tabs.render_links' in page
    assert 'id="resource-profile-workspace"' in page
    assert "('profiles', 'Profile Library'" in page
    assert "('capacity', 'Capacity Governance'" in page
    assert "('workflow', 'Workflow Guide'" in page
    assert "hx_target='#resource-profile-workspace'" in page
    assert "active_resource_profile_view" in page
    assert "active_view not in {'profiles', 'capacity', 'workflow'}" in routes


def test_resource_profile_form_uses_full_width_dense_contract_sections() -> None:
    form = read('app/templates/kubernetes/tenant/partials/_resource_profile_form.html')
    script = read('app/static/js/tenant_resource_profile_presets.js')

    assert 'Create Resource Profile' in form
    assert 'Identity &amp; Lineage' in form
    assert 'Quota Guardrails' in form
    assert 'Container Defaults' in form
    assert 'lg:grid-cols-3' in form
    assert 'lg:grid-cols-5' in form
    assert 'xl:grid-cols-12' not in form
    assert 'Operator rule' in form
    assert 'Custom keeps lineage' in form
    assert 'Different values belong in Custom.' in form
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


def test_capacity_governance_uses_canonical_cluster_budget_table() -> None:
    capacity = read('app/templates/kubernetes/tenant/partials/_capacity_governance.html')
    page = read('app/templates/kubernetes/tenant/resource_profiles.html')
    script = read('app/static/js/tenant_resource_profile_presets.js')
    routes = read('app/kubernetes/tenant/routes.py')
    service = read('app/kubernetes/tenant/service.py')

    assert 'components/table_registry.html' in capacity
    assert 'registry_ui.filter_form' in capacity
    assert 'registry_ui.footer' in capacity
    assert 'capacity_search' in capacity
    assert 'capacity_page' in capacity
    assert 'capacity_per_page' in capacity
    assert 'Budget</th>' in capacity
    assert 'Committed</th>' in capacity
    assert 'Headroom</th>' in capacity
    assert 'State</th>' in capacity
    assert 'space-y-3 p-4' not in capacity
    assert 'Cluster policy uses fresh committed capacity evidence.' in capacity
    assert 'Quota enforces limits; admission uses committed requests, not physical reservation.' in capacity
    assert "action_button.classes('primary', full=true)" in capacity
    assert 'components/status_detail_dialog.html' in capacity

    assert 'tenant-capacity-policy-state' in page
    assert "'capacity_policy_state':" in service
    assert "const policies = readJson('tenant-capacity-policy-state')" in script
    assert 'paginate_sequence' in routes
    assert "context['capacity_pagination']" in routes
    assert "context['capacity_filters']" in routes


def test_capacity_commitment_excludes_deprovisioned_history_and_preserves_unknowns() -> None:
    governance = read('app/kubernetes/tenant/capacity_governance.py')

    assert 'TenantNamespace.provisioning_status != TenantNamespaceProvisioningStatus.DEPROVISIONED.value' in governance
    assert 'def _committed_evidence_reason(committed: CapacityVector)' in governance
    assert 'At least one active Tenant namespace has an unbounded or missing CPU/memory request commitment' in governance
    assert "state = 'Unknown' if commitment_reason" in governance
    assert 'commitment_reason or _state_reason(state)' in governance
