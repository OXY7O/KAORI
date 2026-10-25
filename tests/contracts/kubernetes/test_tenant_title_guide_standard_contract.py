"""Canonical title-adjacent Tenant Guides without field/row tooltip regression (#2363)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TENANT = ROOT / 'app' / 'templates' / 'kubernetes' / 'tenant' / 'partials'

TITLE_GUIDES = {
    '_tenant_registry.html': ('tenant-registry-status-tip',),
    '_tenant_discovery.html': ('tenant-discovery-status-tip',),
    '_group_registry.html': ('tenant-group-lifecycle-tip',),
    '_membership_registry.html': ('tenant-membership-lifecycle-tip',),
    '_tenant_form.html': ('tenant-setup-form-tip', 'capsule-initial-owner-guide-tip'),
    '_tenant_memberships_workspace.html': (
        'membership-user-tip',
        'membership-group-tip',
        'membership-attach-group-tip',
    ),
    '_tenant_access_grants_workspace.html': ('access-grant-form-tip',),
    '_tenant_credentials_workspace.html': ('human-credential-tip', 'deployer-credential-tip'),
    '_tenant_namespace_access_workspace.html': ('namespace-access-tip',),
    '_namespace_form.html': ('namespace-provisioning-contract-tip',),
    '_capacity_governance.html': (
        'tenant-capacity-policy-tip',
        'tenant-capacity-compute-pod-tip',
        'tenant-limit-exposure-policy-tip',
        'tenant-capacity-storage-budget-tip',
        'allocation-budget-status-tip',
    ),
    '_capacity_decisions.html': ('tenant-capacity-decision-tip',),
    '_allocation_change.html': ('namespace-allocation-change-tip',),
    '_allocation_cutover.html': ('allocation-cutover-tip',),
    '_capsule_tenant_quota_cutover.html': ('capsule-tenant-quota-tip',),
    '_capsule_shared_allocation_cutover.html': ('capsule-shared-cutover-tip',),
    '_resource_profile_form.html': (
        'resource-profile-identity-tip',
        'resource-profile-compute-tip',
        'resource-profile-storage-tip',
        'resource-profile-object-tip',
        'resource-profile-limitrange-tip',
    ),
}


def _read(name: str) -> str:
    return (TENANT / name).read_text(encoding='utf-8')


def _tip_expressions(source: str) -> list[str]:
    return re.findall(r'\{\{\s*info_tip\.render\([\s\S]*?\)\s*\}\}', source)


def test_every_approved_tenant_title_guide_uses_shared_variant() -> None:
    for template, identifiers in TITLE_GUIDES.items():
        expressions = _tip_expressions(_read(template))
        for identifier in identifiers:
            matches = [expression for expression in expressions if f"'{identifier}'" in expression]
            assert len(matches) == 1, (template, identifier)
            assert "variant='guide'" in matches[0], (template, identifier)

    advanced = _tip_expressions(_read('_resource_profile_advanced_controls.html'))
    assert len(advanced) == 2
    assert all("variant='guide'" in expression for expression in advanced)


def test_capsule_initial_owner_uses_one_shared_section_guide() -> None:
    source = _read('_tenant_form.html')
    section_start = source.index('Capsule Initial Owner')
    section_end = source.index('Existing Capsule Tenant? Use Discovery', section_start)
    capsule_section = source[section_start:section_end]

    assert capsule_section.count("'capsule-initial-owner-guide-tip'") == 1
    assert "variant='guide'" in capsule_section
    assert 'Owner Kind: User' in capsule_section
    assert 'Owner Kind: Group' in capsule_section
    assert 'Owner Kind: ServiceAccount' in capsule_section
    assert 'Owner Subject must match' in capsule_section
    assert 'oidc:org:platform-team' in capsule_section
    assert 'system:serviceaccount:platform:deployer' in capsule_section
    assert 'capsule-owner-kind-tip' not in capsule_section
    assert 'capsule-owner-subject-tip' not in capsule_section

    # Both labels and required provider controls remain permanently visible.
    assert 'Required for Capsule provider ownership' in capsule_section
    assert 'form_field.label_row("Owner Kind")' in capsule_section
    assert 'form_field.label_row("Owner Subject")' in capsule_section
    assert 'name="capsule_owner_kind"' in capsule_section
    assert 'name="capsule_owner_subject"' in capsule_section
    assert capsule_section.count('data-capsule-owner-control') == 2
    assert 'value="User"' in capsule_section
    assert 'value="Group" selected' in capsule_section
    assert 'value="ServiceAccount"' in capsule_section
    assert capsule_section.count('disabled') == 2


def test_resource_group_guides_are_inside_owning_disclosure_title() -> None:
    source = _read('_resource_profile_form.html')
    assert 'Section help' not in source
    for name, identifier in (
        ('compute', 'resource-profile-compute-tip'),
        ('storage', 'resource-profile-storage-tip'),
        ('object', 'resource-profile-object-tip'),
        ('container', 'resource-profile-limitrange-tip'),
    ):
        heading = f'id="resource-profile-{name}-heading"'
        heading_at = source.index(heading)
        start = source.rfind('<summary', 0, heading_at)
        end = source.index('</summary>', heading_at)
        summary = source[start:end]
        assert heading in summary
        assert identifier in summary
        assert "variant='guide'" in summary
        assert summary.index(heading) < summary.index(identifier)


def test_field_and_row_specific_evidence_remains_icon_only() -> None:
    field_tips = {
        '_tenant_access_grants_workspace.html': (
            'access-membership-tip',
            'access-profile-tip',
            'access-scope-tip',
        ),
        '_tenant_adoption_preflight.html': ('tenant-adoption-control-tip',),
    }
    for template, identifiers in field_tips.items():
        expressions = _tip_expressions(_read(template))
        for identifier in identifiers:
            matches = [expression for expression in expressions if f"'{identifier}'" in expression]
            assert len(matches) == 1, (template, identifier)
            assert "variant='guide'" not in matches[0], (template, identifier)

    reconciliation = _read('_access_grant_registry.html')
    row_tip = next(
        expression for expression in _tip_expressions(reconciliation) if "'access-grant-reconciliation-'" in expression
    )
    assert "variant='guide'" not in row_tip
    assert 'grant.reconciliation_message' in row_tip


def test_hover_portal_gap_and_disclosure_click_are_safe() -> None:
    script = (ROOT / 'app' / 'static' / 'js' / 'info_tips.js').read_text(encoding='utf-8')
    assert 'portal.appendChild(preview)' in script
    assert 'scheduleHide()' in script
    assert 'cancelPendingHide()' in script
    assert "if (trigger.closest('summary')) event.preventDefault()" in script
    assert "document.addEventListener('htmx:beforeSwap', hideActive)" in script
    assert "if (event.key === 'Escape') hideActive()" in script
