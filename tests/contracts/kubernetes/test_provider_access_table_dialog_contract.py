"""Provider evidence follows KAORI's Intelligence expandable-table pattern."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_provider_registries_use_shared_table_and_expandable_row() -> None:
    rows = read('app/templates/kubernetes/tenant/partials/_provider_access_evidence_rows.html')
    detail = read('app/templates/kubernetes/tenant/partials/_provider_access_evidence_detail.html')
    intelligence = read('app/templates/intelligence/partials/_catalog_records.html')
    expandable = read('app/templates/components/details/_expandable_row.html')

    assert 'components/details/_expandable_row.html' in rows
    assert 'detail_row.toggle_button(' in rows
    assert 'detail_row.static_detail_row(detail_row_id, detail_target_id, 5)' in rows
    assert 'table_action=true' in rows
    assert "open_label='View Details'" in rows
    assert "close_label='Hide Details'" in rows
    assert 'detail_row.toggle_button(' in intelligence
    assert 'data-detail-static="true"' in expandable
    assert rows.count('<td class=') == 5
    assert '<td colspan="5"' in rows  # Only for empty state
    assert '<details class=' not in rows
    assert 'grid-cols-[28%_17%_32%_14%_9%]' not in rows
    assert 'data-tenant-provider-evidence-detail' in detail
    assert 'lg:grid-cols-2 lg:divide-x' in detail
    assert 'lg:grid-cols-3' not in detail

    for provider, path in (
        ('capsule', 'app/templates/kubernetes/tenant/partials/_external_capsule_access_inventory.html'),
        ('native', 'app/templates/kubernetes/tenant/partials/_native_namespace_rbac_inventory.html'),
    ):
        ui = read(path)
        assert ui.count('<table class=') == 1
        assert "table_ui.table_classes('min-w-[980px] !table-fixed')" in ui
        assert '_provider_access_evidence_rows.html' in ui
        assert 'table_label.result_count(access_evidence_pagination.total_items)' in ui
        assert "registry_ui.filter_form('tenant.tenants'" in ui
        assert "registry_ui.clear_filters_link('tenant.tenants'" in ui
        assert "registry_ui.footer('tenant.tenants'" in ui
        assert 'lead=false' not in ui
        assert 'class="flex items-end justify-end"' not in ui
        assert '<details class="group min-w-0">' not in ui
        assert 'grid min-w-[970px]' not in ui
        assert f'name="access_inventory_view" value="{provider}"' in ui


def test_committed_drift_and_provider_actions_remain_in_one_expansion() -> None:
    rows = read('app/templates/kubernetes/tenant/partials/_provider_access_evidence_rows.html')
    detail = read('app/templates/kubernetes/tenant/partials/_provider_access_evidence_detail.html')
    assert 'access_evidence_drift_by_tenant.get(evidence.tenant_id)' in rows
    assert 'Drift Findings' in detail
    assert 'Latest independently committed analysis' in detail
    assert 'No committed drift analysis for this Tenant' in detail
    assert 'No automatic remediation was performed.' in detail
    assert 'Effective RBAC was not reverified.' in detail
    assert "finding.code|replace('_', ' ') |title" in detail
    assert 'tenant.analyze_capsule_external_access_route' in detail
    assert 'tenant.analyze_native_access_drift_route' in detail
    assert 'tenant.plan_capsule_access_remediation_route' in detail
    assert 'tenant.review_external_capsule_profile_route' in detail
    assert 'tenant.review_external_native_profile_route' in detail
    assert 'Review Profile Match' in detail
    assert 'Prepare Remediation Decisions' in detail
    assert 'name="binding_uid"' in detail
    assert 'name="binding_index"' in detail
    assert 'binding.claimed_grant_marker' in detail
    assert 'Labels indicate possible correlation' in detail
    assert detail.count('name="csrf_token"') == 4
    assert 'components/table.html' in detail
    assert 'components/table_label.html' in detail
