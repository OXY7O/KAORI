"""Tenant provider evidence uses one expandable table with committed drift correlation."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_provider_evidence_uses_one_table_and_native_row_disclosure() -> None:
    for provider, path in (
        ('capsule', 'app/templates/kubernetes/tenant/partials/_external_capsule_access_inventory.html'),
        ('native', 'app/templates/kubernetes/tenant/partials/_native_namespace_rbac_inventory.html'),
    ):
        ui = read(path)
        assert ui.count('<table class=') == 1
        assert "table_ui.table_classes('min-w-[970px] table-fixed xl:min-w-0')" in ui
        assert '<details class="group min-w-0">' in ui
        assert 'aria-label="Expand ' in ui
        assert 'grid min-w-[970px]' in ui
        assert 'colspan="5"' in ui
        assert 'Provider Evidence' in ui
        assert 'Observed At' in ui
        assert 'Review Required' in ui
        assert "access_evidence_drift_by_tenant.get(evidence.tenant_id)" in ui
        assert "registry_ui.footer('tenant.tenants'" in ui
        assert 'lead=false' in ui
        assert 'name="csrf_token"' in ui
        assert f'name="access_inventory_view" value="{provider}"' in ui
        assert 'Review Profile Match' in ui
        assert 'No committed drift analysis for this Tenant' in ui
        assert 'no automatic remediation was performed.' in ui.lower()
        assert 'data-kaori-native-dialog' not in ui
        assert '<dialog id="tenant-' not in ui
        assert ui.count('{% if ') == ui.count('{% endif %}')
        assert ui.count('{% for ') == ui.count('{% endfor %}')


def test_capsule_drift_is_not_rendered_as_a_second_table() -> None:
    ui = read('app/templates/kubernetes/tenant/partials/_external_capsule_access_inventory.html')
    assert 'Drift Findings' in ui
    assert 'Latest independently committed analysis' in ui
    assert 'finding.code|replace' in ui
    assert 'tenant.plan_capsule_access_remediation_route' in ui
    assert 'Prepare Remediation Decisions' in ui
    assert 'Declaration correlation only.' in ui
    assert 'Effective RBAC was not reverified' in ui
    assert 'tenant-capsule-access-drift-title' not in ui
    assert 'View Findings' not in ui


def test_provider_specific_scope_and_review_are_preserved() -> None:
    capsule = read('app/templates/kubernetes/tenant/partials/_external_capsule_access_inventory.html')
    native = read('app/templates/kubernetes/tenant/partials/_native_namespace_rbac_inventory.html')
    assert 'Observed Owners &amp; Provider Bindings' in capsule
    assert 'review_external_capsule_profile_route' in capsule
    assert 'review_external_native_profile_route' in native
    assert 'binding.claimed_grant_marker' in native
    assert 'Labels indicate possible correlation' in native
    assert 'No membership or RBAC mutation occurs' in capsule
    assert 'does not import IdP users' in capsule
