from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

ADVANCED_CAPABILITIES = (
    'shared_global_quota',
    'resource_pools',
    'replication',
    'proxy',
    'tenant_cordon',
    'namespace_controls',
    'resource_rules',
    'cross_namespace_credential',
    'self_service_namespace',
)


def test_capsule_discovery_exposes_advanced_capabilities_without_native_emulation() -> None:
    source = (ROOT / 'app/kubernetes/tenant/capsule_provider.py').read_text(encoding='utf-8')

    for capability in ADVANCED_CAPABILITIES:
        assert f"'{capability}'" in source
    assert "probes.get('tenant_cordon')" in source
    assert "probes.get('namespace_controls')" in source
    assert "probes.get('resource_rules')" in source
    assert "probes.get('cross_namespace_credential')" in source
    assert "probes.get('self_service_namespace')" in source


def test_advanced_capsule_mutations_use_custom_objects_api_and_capability_gate() -> None:
    client = (
        ROOT / 'app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api/client.py'
    ).read_text(encoding='utf-8')
    source = (ROOT / 'app/kubernetes/tenant/capsule_advanced.py').read_text(encoding='utf-8')

    assert 'def custom_objects_api(' in client
    assert 'require_capsule_capability' in source
    assert 'create_cluster_custom_object' in source
    assert 'patch_cluster_custom_object' in source
    assert 'create_namespaced_custom_object' in source
    assert 'patch_namespaced_custom_object' in source
    assert 'delete_cluster_custom_object' in source
    assert 'delete_namespaced_custom_object' in source
    assert "provider_key != 'capsule'" in source
    assert 'native_kubernetes' not in source


def test_advanced_intent_is_committed_and_audited_without_secret_material() -> None:
    model = (ROOT / 'app/models/tenant_advanced.py').read_text(encoding='utf-8')
    service = (ROOT / 'app/kubernetes/tenant/capsule_advanced_service.py').read_text(encoding='utf-8')
    migration = (ROOT / 'migrations/versions/20260927_tenant_capsule_advanced.py').read_text(encoding='utf-8')

    assert 'class TenantAdvancedCapabilityIntent' in model
    assert 'desired_spec_json' in model
    assert 'effective_spec_json' in model
    assert 'reconciliation_evidence_json' in model
    assert 'tenant_advanced_capability_intents' in migration
    assert "target_type = 'tenant_advanced_capability'" in service
    assert "'secret_material_persisted': False" in service
    assert 'create_advanced_intent_committed' in service
    assert 'reconcile_advanced_intent_committed' in service
    assert 'remove_advanced_intent_committed' in service


def test_capsule_advanced_docs_preserve_single_authority_and_conditional_uat() -> None:
    docs = (ROOT / 'docs/architecture/kubernetes-tenant-capsule-advanced.md').read_text(encoding='utf-8')

    assert 'specific discovered capability' in docs
    assert 'fail closed' in docs
    assert 'single reconciliation authority' in docs
    assert 'Native mode does not emulate' in docs
    assert 'capability-conditional' in docs
    assert 'self-service namespace creation remains disabled' in docs


def test_capsule_tenant_quota_governance_uses_compact_action_footers() -> None:
    source = (ROOT / 'app/templates/kubernetes/tenant/partials/_capsule_tenant_quota_cutover.html').read_text(
        encoding='utf-8'
    )

    assert 'Capsule Tenant Quota Governance' in source
    assert source.count('border-t border-outline-subtle bg-surface-elevated px-4 py-3') == 2
    assert 'Governance Cutover' in source
    assert 'Managed Change' in source
    assert 'Adoption stays read-only until explicit cutover.' in source
    assert 'Resolve drift before applying a new profile.' in source
    assert 'Take Over Governance' in source
    assert 'Change Allocation' in source
    assert 'Take Over Allocation Governance' not in source
    assert 'Change Governed Allocation' not in source

def test_capsule_quota_cutover_comparisons_preserve_distinct_provider_authorities() -> None:
    from jinja2 import Environment

    folder = ROOT / 'app/templates/kubernetes/tenant/partials'
    shared = (folder / '_capsule_shared_allocation_cutover.html').read_text(encoding='utf-8')
    tenant = (folder / '_capsule_tenant_quota_cutover.html').read_text(encoding='utf-8')
    script = (ROOT / 'app/static/js/tenant_resource_profile_presets.js').read_text(encoding='utf-8')
    env = Environment(autoescape=True)
    env.parse(shared)
    env.parse(tenant)

    for template in (shared, tenant):
        assert 'Managed Contract Comparison' in template
        assert 'Change Highlights' in template
        assert 'grid md:grid-cols-2' in template
        assert 'ResourceQuota' in template or 'Tenant.spec.resourceQuotas' in template
        assert 'data-tenant-quota-metric-side=' in template
        assert 'data-tenant-quota-metric-key="{{ key }}"' in template
        for dimension in ('requests.cpu', 'limits.cpu', 'requests.memory',
                          'limits.memory', 'pods', 'requests.storage'):
            assert f"'{dimension}'" in template
        assert 'data-tenant-quota-change-summary aria-live="polite"' in template
        assert 'name="csrf_token"' in template
        assert 'border border-outline-subtle bg-surface-card shadow-sm' in template

    # Shared GlobalResourceQuota eligibility and alternative-authority
    # explanations remain separate from Capsule Tenant.spec.resourceQuotas.
    assert "url_for('tenant.cutover_capsule_shared_allocation_route')" in shared
    assert 'data-tenant-shared-allocation-tenant' in shared
    assert 'data-tenant-shared-allocation-profile' in shared
    assert "not can_manage or not capsule_shared_cutover_supported or not profiles" in shared
    assert "capsule_shared_cutover_state.values()" in shared
    assert 'Other allocation authorities' in shared
    assert 'Not applicable here' in shared
    assert 'Control Unavailable' in shared
    assert 'Committed GRQ sources:' in shared
    assert 'GlobalResourceQuota/' in script
    assert 'current ? current.current_quota || {} : null' in script

    # Tenant CR cutover and managed-change remain distinct POSTs, preserving
    # provider scope and external LimitRange observations.
    assert "url_for('tenant.cutover_capsule_tenant_quota_route')" in tenant
    assert "url_for('tenant.change_capsule_tenant_quota_route')" in tenant
    assert tenant.count('data-tenant-quota-change-summary aria-live="polite"') == 2
    assert tenant.count('data-tenant-quota-metric-side=') == 2
    assert 'data-tenant-quota-current-scope' in tenant
    assert 'data-tenant-quota-managed-summary' in tenant
    assert 'data-tenant-quota-managed-proposed-profile' in tenant
    assert 'external_constraints' in tenant
    assert 'not can_manage or not capsule_tenant_quota_cutover_supported or not profiles' in tenant
    assert 'not can_manage or not capsule_tenant_quota_managed or not profiles' in tenant

    assert 'const renderCapsuleQuotaPreview = (form, current, proposed) => {' in script
    assert "form.querySelectorAll('[data-tenant-quota-metric-side]')" in script
    assert "summary.textContent = 'Choose contracts'" in script
    assert 'No quota differences' in script
    assert 'of 6 quota dimensions differ · Read only' in script
    assert 'state ? state.desired_quota || {} : null' in script
    assert 'tenantSelect?.addEventListener(\'change\', render)' in script
    assert 'profileSelect?.addEventListener(\'change\', render)' in script
