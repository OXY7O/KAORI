"""Lock bounded Tenant tables without changing provider or lifecycle behavior."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TENANT = ROOT / 'app/templates/kubernetes/tenant/partials'

# Each width profile reflects the existing table's content and action density.
REGISTRIES = {
    '_cluster_estate': (900, (29, 11, 13, 16, 17, 14)),
    # Resource Profile Registry is responsive under #2367; dedicated
    # workspace contracts assert no forced minimum or horizontal overflow.
    '_tenant_registry': (1040, (20, 19, 12, 9, 15, 13, 12)),
    '_namespace_registry': (1080, (25, 18, 32, 15, 10)),
    # Settings-style Memberships tables fit desktop with narrow-only table-local scrolling.
    '_group_registry': (840, (18, 15, 17, 12, 12, 26)),
    '_membership_registry': (800, (23, 20, 14, 13, 15, 15)),
    '_operations_drift_registry': (1420, (17, 16, 19, 28, 20)),
    '_operations_provider_registry': (980, (23, 28, 31, 18)),
    '_operations_namespace_registry': (1100, (23, 20, 27, 15, 15)),
    '_operations_access_reconciliation_registry': (1100, (22, 20, 25, 12, 21)),
    '_capsule_shared_allocation_drift': (1450, (19, 23, 35, 23)),
    '_capsule_tenant_quota_drift': (1450, (19, 23, 35, 23)),
}
EVIDENCE_VARIANTS = (
    (19, 16, 16, 14, 20, 15),  # audit
    (26, 27, 15, 15, 17),  # managed resource
    (27, 25, 15, 15, 18),  # domain reservation
    (20, 18, 18, 20, 12, 12),  # exposure policy
)


def _template(name: str) -> str:
    return (TENANT / f'{name}.html').read_text(encoding='utf-8')


def _header_widths(html: str) -> tuple[int, ...]:
    head = html.split('<thead', 1)[1].split('</thead>', 1)[0]
    return tuple(int(x) for x in re.findall(r'<th[^>]*?w-\[([0-9]+)%\]', head))


def test_tenant_registry_tables_use_bounded_existing_table_primitives() -> None:
    for name, (minimum_width, percentages) in REGISTRIES.items():
        template = _template(name)
        if name in {'_membership_registry', '_group_registry'}:
            assert f'min-w-[{minimum_width}px] table-fixed xl:min-w-0' in template, name
            assert 'w-full min-w-0 max-w-full overflow-x-auto' in template, name
        else:
            assert f'min-w-[{minimum_width}px] !table-fixed' in template, name
        assert _header_widths(template) == percentages, name
        assert sum(percentages) == 100, name
        assert 'overflow-x-auto' in template, name
        assert 'table_ui.cell_classes(' in template, name
        assert 'truncate' in template, name
        assert 'title=' in template, name


def test_allocation_budget_registry_uses_owned_bounded_responsive_evidence_table() -> None:
    # The policy form owns the Capacity subview, not a legacy embedded table.
    policy = _template('_capacity_governance')
    budget = _template('_allocation_budget_registry')
    detail = _template('_allocation_budget_detail')

    assert "('budget', 'Allocation Budget', 'table-2'" in policy
    assert 'workspace_tabs.render_query_tabs(allocation_tabs,' in policy
    assert "active_allocation_view == 'budget'" in policy
    assert '_allocation_budget_registry.html' in policy
    assert 'table_ui.table_classes(' not in policy

    # Approved responsive five-column table, with local narrow-screen scrolling.
    assert "table_ui.table_classes('min-w-[760px] table-fixed xl:min-w-0')" in budget
    assert 'min-w-[980px]' not in budget
    assert _header_widths(budget) == (29, 20, 20, 16, 15)
    assert sum(_header_widths(budget)) == 100
    assert 'overflow-x-auto xl:overflow-visible' in budget
    assert 'table_ui.cluster_identity(item.cluster.name, item.cluster.environment)' in budget
    assert 'table_label.status_label(item.state, state_tone)' in budget
    assert 'table_label.status_label(' in budget
    assert 'item.committed_namespace_count' in budget

    # Committed evidence and resource headroom stay behind accessible details.
    assert "detail_row.toggle_button('tenant-capacity-budget'" in budget
    assert 'detail_row.static_detail_row(detail_row_id, detail_target_id, 5' in budget
    assert '_allocation_budget_detail.html' in budget
    assert 'capacity-budget-registry' in budget
    assert 'registry_ui.filter_form(' in budget
    assert "registry_ui.footer('tenant.resource_profiles'" in budget
    assert 'aria-label="{{ bar.label }} allocation evidence"' in detail
    assert 'bar.budget' in detail and 'bar.committed' in detail and 'bar.headroom' in detail
    assert 'Ratio unavailable — no free headroom is asserted.' in detail


def test_namespace_access_registry_uses_responsive_five_column_evidence_table() -> None:
    registry = _template('_namespace_access_registry')
    detail = _template('_namespace_access_detail')
    assert 'min-w-[1400px]' not in registry
    assert 'overflow-x-auto' not in registry
    assert 'min-w-[1400px] !table-fixed' not in registry
    assert "table_ui.table_classes('!table-fixed')" in registry
    assert _header_widths(registry) == (25, 20, 25, 15, 15)
    assert 'Tenant / Scope' in registry
    assert "access.get('environment')|default('Not assigned', true)|title" in registry
    assert 'hidden w-full min-w-0 lg:block' in registry
    assert 'lg:hidden' in registry
    assert '<td colspan="5"' in registry
    assert 'detail_row.static_detail_row(detail_row_id, detail_target_id, 5' in registry
    assert "detail_row.toggle_button('tenant-namespace-access'" in registry
    assert '_namespace_access_detail.html' in registry
    assert 'data-tenant-namespace-access-mobile-detail' in registry
    assert 'data-tenant-namespace-access-detail' in detail
    assert 'Approved Access Methods' in detail
    assert 'Valid Until' in detail
    assert 'Credential Reference' in detail
    assert 'No token, kubeconfig, private key, certificate, or Secret material' in detail
    assert 'credential.token' not in detail
    assert 'credential.kubeconfig' not in detail
    assert 'get(&quot;' not in registry


def test_namespace_access_detail_has_grouped_visual_hierarchy_and_safe_provenance() -> None:
    registry = _template('_namespace_access_registry')
    detail = _template('_namespace_access_detail')
    assert 'data-tenant-namespace-access-detail' in detail
    assert 'Committed Namespace Access' in detail
    assert 'aria-label="Access package summary"' in detail
    assert 'Identity &amp; Authorization' in detail
    assert 'aria-label="Identity and authorization"' in detail
    assert 'Credential Lifecycle' in detail
    assert 'aria-label="Credential lifecycle"' in detail
    assert 'aria-label="Technical references"' in detail
    assert 'Security' not in registry.split('<thead', 1)[1].split('</thead>', 1)[0]
    assert 'No token, kubeconfig, private key, certificate, or Secret material' in detail
    assert 'No effective access is asserted by this record.' in detail
    assert 'table_label.status_label(' in detail
    assert 'table_label.metadata_label(' in detail
    assert "access.get('credential_public_id')" in detail
    assert "access.get('renewal_due_at')|user_datetime" in detail
    assert "access.get('valid_until')|user_datetime" in detail
    assert "access.get('approved_access_methods') or []" in detail
    assert 'bg-surface-elevated' in detail
    assert 'bg-surface-hover' in detail
    assert 'min-w-[1400px]' not in registry
    assert 'overflow-x-auto' not in registry
    assert 'credential.token' not in detail
    assert 'credential.kubeconfig' not in detail


def test_access_grant_registry_uses_the_approved_responsive_fixed_table() -> None:
    # This registry intentionally fits the desktop viewport and keeps a compact
    # 1040px minimum on narrow screens, unlike the overflow-first registries.
    template = _template('_access_grant_registry')
    widths = (19, 14, 13, 17, 17, 20)
    assert "table_ui.table_classes('min-w-[1040px] table-fixed xl:min-w-0')" in template
    assert _header_widths(template) == widths
    assert sum(widths) == 100
    assert 'overflow-x-auto' in template
    assert 'table_ui.cell_classes(' in template
    assert 'header_cell_classes(action=true)' in template
    assert 'cell_classes(action=true)' in template
    assert 'title=' in template


def test_tenant_discovery_desktop_fit_with_bounded_narrow_table_overflow() -> None:
    discovery = _template('_tenant_discovery')
    shared = (ROOT / 'app/templates/components/table.html').read_text(encoding='utf-8')

    # No 1300px minimum can force desktop's Review CTA out of view.
    assert 'min-w-[1300px]' not in discovery
    assert "table_ui.table_classes('min-w-[960px] lg:min-w-0 !table-fixed')" in discovery
    assert 'class="w-full min-w-0 max-w-full overflow-x-auto"' in discovery
    assert _header_widths(discovery) == (20, 16, 11, 9, 14, 13, 17)
    assert sum(_header_widths(discovery)) == 100
    assert discovery.count('scope="col"') == 7

    # Preserve every other table's existing shared Cluster Identity default.
    assert "macro cluster_identity(name, environment='', container_width='min-w-[12rem]')" in shared
    assert 'class="flex {{ container_width }} items-start gap-2.5"' in shared
    assert "cluster_identity(row.cluster.name, row.cluster.environment, 'min-w-0 max-w-full')" in discovery

    assert 'class="{{ table_ui.action_classes() }} min-w-0 max-w-full text-center"' in discovery
    assert 'data-tenant-adoption-load' in discovery
    assert 'Review Adoption' in discovery and 'Review Attachment' in discovery
    assert 'hx-target="#tenant-adoption-preflight-slot"' in discovery
    assert 'colspan="7"' in discovery
    assert "registry_ui.footer('tenant.tenants'" in discovery


def test_operational_evidence_table_preserves_each_conditional_column_model() -> None:
    template = _template('_operations_evidence_registry')
    assert 'min-w-[1350px] !table-fixed' in template
    flattened = _header_widths(template)
    assert flattened == tuple(x for variant in EVIDENCE_VARIANTS for x in variant)
    assert all(sum(variant) == 100 for variant in EVIDENCE_VARIANTS)
    for evidence_type in ('audit', 'managed-resource', 'domain-reservation', 'exposure-policy'):
        assert f"evidence_type == '{evidence_type}'" in template
    assert 'truncate' in template
    assert 'table_ui.title_cell(' in template


def test_destructive_and_multi_action_cells_have_reserved_width() -> None:
    for name in (
        '_group_registry',
        '_access_grant_registry',
        '_operations_drift_registry',
        '_capsule_shared_allocation_drift',
        '_capsule_tenant_quota_drift',
    ):
        template = _template(name)
        assert 'header_cell_classes(action=true)' in template, name
        assert 'cell_classes(action=true)' in template, name
        assert 'overflow-x-auto' in template, name
        # Actions are not hidden or reduced to ellipsis.
        assert 'truncate' not in template.split('cell_classes(action=true)', 1)[1].split('">', 1)[0], name


def test_existing_canonical_fixed_tables_are_not_unnecessarily_modified() -> None:
    credential = _template('_credential_registry')
    decisions = _template('_capacity_decisions')
    assert "table_ui.table_classes('min-w-[760px] table-fixed lg:min-w-0')" in credential
    # Capacity decisions have an approved wider bounded record shape, with an
    # explicit action column and shared horizontal overflow on compact screens.
    assert "table_ui.table_classes('min-w-[1060px] !table-fixed')" in decisions
    assert 'overflow-x-auto' in decisions
    assert 'header_cell_classes(action=true)' in decisions
    assert 'cell_classes(action=true)' in decisions


def test_tooltip_expressions_are_not_html_entity_encoded_inside_jinja() -> None:
    for name in (*REGISTRIES, '_operations_evidence_registry'):
        template = _template(name)
        assert 'get(&quot;' not in template, name


def test_tenant_registry_keeps_compact_namespace_summary_and_full_page_history() -> None:
    template = _template('_tenant_registry')
    table = template.split('<table', 1)[1].split('</table>', 1)[0]
    detail = (ROOT / 'app/templates/kubernetes/tenant/partials/_tenant_management_detail.html').read_text()

    # The Registry stays compact; full committed history resides in a detail
    # page, not below the table or behind the native dialog top layer.
    assert 'min-w-[1300px]' not in table
    assert 'min-w-[1040px] !table-fixed' in table
    assert 'w-[9%]">Namespaces</th>' in table
    assert 'historical Namespace record' not in table
    assert 'Active managed namespaces' not in table
    assert 'row.namespace_count }} <span class="text-xs font-normal' in table
    assert 'historical Namespace record' in detail
    assert 'row.namespace_history_count - row.namespace_count' in detail
    assert 'aria-label="Tenant management sections"' in detail
    assert 'tenant.tenant_detail' in template
    assert 'data-kaori-dialog-preserve-on-swap' not in template
    assert 'data-kaori-dialog-open' not in template
    assert 'data-destructive-modal-open' in detail


def test_tenant_registry_lifecycle_and_actions_fit_the_compact_layout() -> None:
    template = _template('_tenant_registry')
    table = template.split('<table', 1)[1].split('</table>', 1)[0]
    assert 'w-[19%]">Cluster' in table
    assert 'w-[12%]">Actions' in table
    assert 'block min-w-0 max-w-full truncate text-xs text-content-muted' in table
    assert 'title="{{ tenant.ownership_status' in table
    assert 'class="{{ table_ui.action_classes() }} shrink-0"' in table
