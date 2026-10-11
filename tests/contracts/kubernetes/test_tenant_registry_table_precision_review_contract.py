"""Lock bounded Tenant tables without changing provider or lifecycle behavior."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TENANT = ROOT / "app/templates/kubernetes/tenant/partials"

# Each width profile reflects the existing table's content and action density.
REGISTRIES = {
    "_cluster_estate": (900, (29, 11, 13, 16, 17, 14)),
    "_resource_profile_registry": (1150, (43, 16, 17, 12, 12)),
    "_tenant_registry": (1040, (20, 19, 12, 9, 15, 13, 12)),
    "_namespace_registry": (1100, (19, 19, 30, 16, 16)),
    "_group_registry": (1250, (18, 15, 17, 12, 12, 26)),
    "_membership_registry": (1100, (23, 20, 14, 13, 15, 15)),
    "_access_grant_registry": (1300, (18, 14, 13, 14, 15, 26)),
    "_namespace_access_registry": (1400, (16, 17, 13, 17, 12, 12, 13)),
    "_operations_drift_registry": (1420, (17, 16, 19, 28, 20)),
    "_operations_provider_registry": (1100, (22, 23, 17, 23, 15)),
    "_operations_namespace_registry": (1100, (23, 20, 27, 15, 15)),
    "_operations_access_reconciliation_registry": (1100, (22, 20, 25, 12, 21)),
    "_capacity_governance": (980, (30, 38, 14, 18)),
    "_capsule_shared_allocation_drift": (1450, (19, 23, 35, 23)),
    "_capsule_tenant_quota_drift": (1450, (19, 23, 35, 23)),
}
EVIDENCE_VARIANTS = (
    (19, 16, 16, 14, 20, 15),  # audit
    (26, 27, 15, 15, 17),      # managed resource
    (27, 25, 15, 15, 18),      # domain reservation
    (20, 18, 18, 20, 12, 12),  # exposure policy
)


def _template(name: str) -> str:
    return (TENANT / f"{name}.html").read_text(encoding="utf-8")


def _header_widths(html: str) -> tuple[int, ...]:
    head = html.split("<thead", 1)[1].split("</thead>", 1)[0]
    return tuple(
        int(x) for x in re.findall(r"<th[^>]*?w-\[([0-9]+)%\]", head)
    )


def test_tenant_registry_tables_use_bounded_existing_table_primitives() -> None:
    for name, (minimum_width, percentages) in REGISTRIES.items():
        template = _template(name)
        assert f"min-w-[{minimum_width}px] !table-fixed" in template, name
        assert _header_widths(template) == percentages, name
        assert sum(percentages) == 100, name
        assert "overflow-x-auto" in template, name
        assert "table_ui.cell_classes(" in template, name
        assert "truncate" in template, name
        assert "title=" in template, name


def test_tenant_discovery_desktop_fit_with_bounded_narrow_table_overflow() -> None:
    discovery = _template("_tenant_discovery")
    shared = (ROOT / "app/templates/components/table.html").read_text(encoding="utf-8")

    # No 1300px minimum can force desktop's Review CTA out of view.
    assert "min-w-[1300px]" not in discovery
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
    template = _template("_operations_evidence_registry")
    assert "min-w-[1350px] !table-fixed" in template
    flattened = _header_widths(template)
    assert flattened == tuple(x for variant in EVIDENCE_VARIANTS for x in variant)
    assert all(sum(variant) == 100 for variant in EVIDENCE_VARIANTS)
    for evidence_type in ("audit", "managed-resource", "domain-reservation", "exposure-policy"):
        assert f"evidence_type == '{evidence_type}'" in template
    assert "truncate" in template
    assert "table_ui.title_cell(" in template


def test_destructive_and_multi_action_cells_have_reserved_width() -> None:
    for name in (
        "_group_registry", "_access_grant_registry",
        "_operations_drift_registry", "_capsule_shared_allocation_drift",
        "_capsule_tenant_quota_drift",
    ):
        template = _template(name)
        assert "header_cell_classes(action=true)" in template, name
        assert "cell_classes(action=true)" in template, name
        assert "overflow-x-auto" in template, name
        # Actions are not hidden or reduced to ellipsis.
        assert "truncate" not in template.split("cell_classes(action=true)", 1)[1].split('">', 1)[0], name


def test_existing_canonical_fixed_tables_are_not_unnecessarily_modified() -> None:
    credential = _template("_credential_registry")
    decisions = _template("_capacity_decisions")
    assert "table_ui.table_classes('min-w-[760px] table-fixed lg:min-w-0')" in credential
    assert "table_ui.table_classes('table-fixed')" in decisions


def test_tooltip_expressions_are_not_html_entity_encoded_inside_jinja() -> None:
    for name in (*REGISTRIES, "_operations_evidence_registry"):
        template = _template(name)
        assert "get(&quot;" not in template, name



def test_tenant_registry_keeps_compact_namespace_summary_and_full_page_history() -> None:
    template = _template("_tenant_registry")
    table = template.split("<table", 1)[1].split("</table>", 1)[0]
    detail = (ROOT / "app/templates/kubernetes/tenant/partials/_tenant_management_detail.html").read_text()

    # The Registry stays compact; full committed history resides in a detail
    # page, not below the table or behind the native dialog top layer.
    assert "min-w-[1300px]" not in table
    assert "min-w-[1040px] !table-fixed" in table
    assert 'w-[9%]">Namespaces</th>' in table
    assert "historical Namespace record" not in table
    assert "Active managed namespaces" not in table
    assert 'row.namespace_count }} <span class="text-xs font-normal' in table
    assert "historical Namespace record" in detail
    assert "row.namespace_history_count - row.namespace_count" in detail
    assert 'aria-label="Tenant management sections"' in detail
    assert 'tenant.tenant_detail' in template
    assert "data-kaori-dialog-preserve-on-swap" not in template
    assert 'data-kaori-dialog-open' not in template
    assert "data-destructive-modal-open" in detail


def test_tenant_registry_lifecycle_and_actions_fit_the_compact_layout() -> None:
    template = _template("_tenant_registry")
    table = template.split("<table", 1)[1].split("</table>", 1)[0]
    assert 'w-[19%]">Cluster' in table
    assert 'w-[12%]">Actions' in table
    assert 'block min-w-0 max-w-full truncate text-xs text-content-muted' in table
    assert 'title="{{ tenant.ownership_status' in table
    assert 'class="{{ table_ui.action_classes() }} shrink-0"' in table
