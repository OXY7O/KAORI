from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_resource_profiles_page_uses_operational_allocation_workflow() -> None:
    page = read('app/templates/kubernetes/tenant/resource_profiles.html')

    assert 'components/operational_flow_steps.html' in page
    assert 'components/operational_section_card.html' in page
    assert 'components/section_intro.html' in page
    assert 'Allocation Workflow' in page
    assert 'Resource Profile Flow' in page
    assert 'Profile Contract' in page
    assert 'Capacity Guardrail' in page
    assert 'Provision Namespace' in page
    assert 'Verify Evidence' in page
    assert 'Profile Library' in page
    assert 'Capacity Governance' in page
    assert 'Ready for Namespace' in page
    assert 'Continue to Namespace' in page
    assert "_resource_profile_registry.html" in page
    assert "xl:grid-cols-[minmax(0,1.25fr)_minmax(20rem,0.75fr)]" not in page


def test_resource_profile_form_separates_identity_quota_and_container_contracts() -> None:
    form = read('app/templates/kubernetes/tenant/partials/_resource_profile_form.html')
    script = read('app/static/js/tenant_resource_profile_presets.js')

    assert 'Create Resource Profile' in form
    assert 'Identity &amp; Lineage' in form
    assert 'Quota Guardrails' in form
    assert 'Container Defaults' in form
    assert 'resource-profile-contract-tip' in form
    assert 'resource-profile-class-tip' in form
    assert 'resource-profile-base-tip' in form
    assert 'resource-profile-quota-tip' in form
    assert 'resource-profile-limitrange-tip' in form
    assert 'data-tenant-profile-class' in form
    assert 'data-tenant-base-preset' in form
    assert form.count('data-tenant-resource-field=') == 14
    assert 'Profile creation commits reusable intent only.' in form
    assert 'Create Profile' in form

    assert 'setReadonly(fields, true)' in script
    assert "classSelect?.value === 'custom'" in script
    assert 'basePreset?.value ? presets[basePreset.value] : null' in script


def test_resource_profile_registry_exposes_effective_contract_and_lineage() -> None:
    registry = read('app/templates/kubernetes/tenant/partials/_resource_profile_registry.html')

    assert 'Resource Profile Registry' in registry
    assert 'Committed reusable contracts' in registry
    assert 'Requests' in registry
    assert 'Namespace Quota' in registry
    assert 'Container Defaults' in registry
    assert 'Lineage' in registry
    assert 'Based on' in registry
    assert 'Independent Custom' in registry
    assert 'KAORI Preset' in registry
    assert 'Locked · versioned' in registry
    assert '_pagination_footer.html' in registry
    assert "min-w-[1040px]" in registry


def test_capacity_governance_uses_policy_budget_and_state_guidance() -> None:
    capacity = read('app/templates/kubernetes/tenant/partials/_capacity_governance.html')

    assert 'xl:grid-cols-12' in capacity
    assert 'Capacity Policy' in capacity
    assert 'Allocation Budget' in capacity
    assert 'tenant-capacity-policy-tip' in capacity
    assert 'tenant-allocation-budget-tip' in capacity
    assert 'tenant-capacity-state-' in capacity
    assert 'ResourceQuota remains an enforcement primitive.' in capacity
    assert 'fresh committed evidence' in capacity
    assert 'Save Policy' in capacity
