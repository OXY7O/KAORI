"""Provider access observations use a table-first committed evidence review workspace."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_provider_evidence_tables_reuse_shared_registry_and_native_dialogs() -> None:
    for provider, path in (
        ('capsule', 'app/templates/kubernetes/tenant/partials/_external_capsule_access_inventory.html'),
        ('native', 'app/templates/kubernetes/tenant/partials/_native_namespace_rbac_inventory.html'),
    ):
        ui = read(path)
        assert "table_ui.table_classes('min-w-[1050px] table-fixed xl:min-w-0')" in ui
        assert 'scope="col"' in ui
        assert 'Observed At' in ui
        assert 'Access' in ui or 'RBAC' in ui
        assert '{% for event in access_evidence_rows %}' in ui
        assert 'access_evidence_pagination.allowed_per_page' in ui
        assert "registry_ui.footer('tenant.tenants'" in ui
        assert 'data-kaori-dialog-open' in ui
        assert 'data-kaori-native-dialog' in ui
        assert f'data-dialog-target="tenant-{provider}-evidence-' in ui
        assert f'<dialog id="tenant-{provider}-evidence-' in ui
        assert 'data-kaori-dialog-close' in ui
        assert 'max-h-[calc(100dvh-2rem)]' in ui
        assert 'aria-haspopup="dialog"' in ui
        assert "Review Profile Match" in ui
        assert 'Analyze Drift' in ui
        assert 'name="csrf_token"' in ui
        assert f'name="access_inventory_view" value="{provider}"' in ui
        assert 'Opening this dialog does not reverify effective Kubernetes access.' in ui
        assert '<article class="rounded-lg' not in ui
        assert '<details class="group mt-3' not in ui
        assert ui.index("registry_ui.footer('tenant.tenants'") < ui.index(
            f'<dialog id="tenant-{provider}-evidence-'
        )
        assert ui.count('{% if ') == ui.count('{% endif %}')
        assert ui.count('{% for ') == ui.count('{% endfor %}')


def test_capsule_drift_findings_use_separate_table_and_review_dialog() -> None:
    ui = read('app/templates/kubernetes/tenant/partials/_external_capsule_access_inventory.html')
    assert 'Latest Committed Access Drift Findings' in ui
    assert 'tenant-capsule-access-drift-title' in ui
    assert 'data-dialog-target="tenant-capsule-drift-{{ event.id }}"' in ui
    assert '<dialog id="tenant-capsule-drift-{{ event.id }}"' in ui
    assert 'View Findings' in ui
    assert 'finding.code|replace' in ui
    assert 'Prepare Remediation Decisions' in ui
    assert 'Declaration correlation only.' in ui
    assert 'Effective RBAC was not reverified' in ui
    assert 'no automatic remediation was performed' in ui


def test_modal_evidence_is_distinct_for_capsule_and_native_providers() -> None:
    capsule = read('app/templates/kubernetes/tenant/partials/_external_capsule_access_inventory.html')
    native = read('app/templates/kubernetes/tenant/partials/_native_namespace_rbac_inventory.html')
    assert 'Observed Capsule Owners' in capsule
    assert 'Provider Bindings' in capsule
    assert 'No provider bindings observed in the committed inspection.' in capsule
    assert 'Observed Namespaces' in native
    assert 'Observed RoleBindings' in native
    assert 'binding.claimed_grant_marker' in native
    assert 'Labels indicate possible correlation' in native
    assert 'No membership or RBAC mutation occurs' in capsule
    assert 'does not import IdP users' in capsule
