"""Guide label only on approved title-level KAORI Info Tips (#1680)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app' / 'templates'

TITLE_GUIDE_TEMPLATES = (
    *(
        f'kubernetes/inventory/{resource}/partials/_table_card.html'
        for resource in (
            'configuration',
            'ingresses',
            'namespaces',
            'nodes',
            'pods',
            'services',
            'storage',
            'workloads',
        )
    ),
    'kubernetes/inventory/overview/partials/_resources_by_cluster.html',
    'kubernetes/inventory/topology/partials/_workspace.html',
    'kubernetes/governance/tls_certificates/partials/_table.html',
    'storage/object_storage/inventory/systems/partials/_table_card.html',
    'storage/object_storage/inventory/buckets/partials/_table_card.html',
    'artifact_registry/partials/_inventory_workspace.html',
    'access/activity_audit/partials/_activity_table_card.html',
    'access/activity_audit/partials/_administrative_evidence.html',
    'access/identity_providers/form.html',
    'access/identity_providers/partials/_registry.html',
    'access/identity_providers/partials/_directory_provisioning_strip.html',
    'access/identity_providers/partials/_sso_configuration.html',
    'access/identity_providers/partials/_ldap_configuration.html',
    'artifact_registry/partials/_security_workspace.html',
    'integrations/partials/_domain_workspace.html',
    'platform_operations/data_lifecycle/index.html',
    'kubernetes/tenant/partials/_tenant_discovery.html',
    'kubernetes/tenant/partials/_tenant_form.html',
    'kubernetes/tenant/partials/_tenant_memberships_workspace.html',
    'kubernetes/tenant/partials/_tenant_access_grants_workspace.html',
    'kubernetes/tenant/partials/_tenant_credentials_workspace.html',
    'kubernetes/tenant/partials/_tenant_namespace_access_workspace.html',
    'kubernetes/tenant/partials/_namespace_form.html',
    'kubernetes/tenant/partials/_capacity_decisions.html',
    'kubernetes/tenant/partials/_capacity_governance.html',
    'kubernetes/tenant/partials/_allocation_change.html',
    'kubernetes/tenant/partials/_allocation_cutover.html',
    'kubernetes/tenant/partials/_capsule_shared_allocation_cutover.html',
    'kubernetes/tenant/partials/_capsule_tenant_quota_cutover.html',
    'kubernetes/tenant/partials/_resource_profile_form.html',
    'kubernetes/tenant/partials/_resource_profile_advanced_controls.html',
    'kubernetes/tenant/partials/_tenant_registry.html',
    'kubernetes/tenant/partials/_group_registry.html',
    'kubernetes/tenant/partials/_membership_registry.html',
)


def _read(template: str) -> str:
    return (TEMPLATES / template).read_text(encoding='utf-8')


def test_title_level_guides_use_canonical_variant_and_preserve_scope() -> None:
    for template in TITLE_GUIDE_TEMPLATES:
        source = _read(template)
        assert 'info_tip.render(' in source, template
        assert "variant='guide'" in source, template
        # Data Lifecycle uses the approved top placement to avoid its header edge.
        expected_placement = 'top' if template == 'platform_operations/data_lifecycle/index.html' else 'right'
        assert f"placement='{expected_placement}'" in source, template

    artifact = _read('artifact_registry/partials/_inventory_workspace.html')
    assert artifact.count("variant='guide'") == 3
    assert 'title_extra=registry_title_tip' in artifact

    for template in (
        'kubernetes/tenant/partials/_tenant_registry.html',
        'kubernetes/tenant/partials/_group_registry.html',
        'kubernetes/tenant/partials/_membership_registry.html',
    ):
        source = _read(template)
        assert 'title_extra=title_info' in source


def test_guide_variant_keeps_inline_field_help_default_icon() -> None:
    component = _read('components/info_tip.html')
    script = (ROOT / 'app/static/js/info_tips.js').read_text(encoding='utf-8')
    assert "variant='icon'" in component
    assert "guide_variant = variant == 'guide' and not button_text" in component
    assert 'data-kaori-info-tip-trigger' in component
    assert 'data-kaori-info-tip-preview' in component
    assert 'aria-controls="{{ id }}-tooltip"' in component
    assert 'portal.appendChild(preview)' in script
    assert "document.addEventListener('htmx:beforeSwap'" in script
