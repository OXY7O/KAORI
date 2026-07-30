from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_node_inventory_uses_canonical_resource_page_structure() -> None:
    hero = read("app/templates/inventory/nodes/partials/_hero.html")
    summary = read("app/templates/inventory/nodes/partials/_summary_cards.html")
    table = read("app/templates/inventory/nodes/partials/_table_card.html")

    assert "page_hero.context_card" in hero
    assert "Total CPU" not in hero
    assert "Total Memory" not in hero
    assert "Nodes in Scope" in hero
    assert "Active Signals" in hero
    assert 'components/operational_section_card.html' in summary
    assert 'components/resource_posture_grid.html' in summary
    assert "Node Resource Posture" in summary
    assert "table_ui.inventory_block_header" in table
    assert "table_ui.filter_select_classes" in table
    assert "Search Nodes" in table


def test_node_table_is_compact_and_uses_canonical_labels_and_values() -> None:
    content = read("app/templates/inventory/nodes/partials/_table_content.html")

    for header in ("Node", "Cluster", "Readiness", "Role", "Capacity", "Network", "Details"):
        assert f">{header}<" in content
    for removed in (">Internal IP<", ">CPU<", ">Memory<", ">Storage<"):
        assert removed not in content

    assert "status_indicator_label(node.status_display" in content
    assert "metadata_label(node.role_display)" in content
    assert "components/technical_value.html" in content
    assert 'resource_detail_modal.detail_button(' in content
    assert 'expandable.detail_row(' not in content
    assert '>Rows</label>' in content
    assert "hx_target='#nodes-table-content'" in content


def test_node_readiness_semantics_and_posture_signals_are_normalized_in_service() -> None:
    service = read("app/inventory/resources/nodes.py")

    assert "elif not_ready_nodes == total_nodes:" in service
    assert "readiness_tone, readiness_label = 'critical', 'Critical'" in service
    assert "unknown_nodes" in service
    assert "cordoned_nodes" in service
    assert "pressure_nodes" in service
    assert "network_issue_nodes" in service
    assert "'status_tone':" in service
    assert "else 'unknown'" in service


def test_node_detail_uses_inline_detail_style_shared_primitives_and_operational_context() -> None:
    detail = read("app/templates/inventory/nodes/partials/_node_detail_content.html")
    shared = read("app/templates/components/details/_detail_content.html")

    assert 'data-kaori-detail-variant="full-workspace-modal"' in detail
    assert 'components/details/_detail_content.html' in detail
    assert "Node Capacity" in detail
    assert "Kernel Version" in detail
    assert "Container Runtime" in detail
    assert "Kubelet Version" in detail
    assert "Kube-Proxy Version" in detail
    assert "Committed Snapshot Boundary" in detail
    assert "node.operational_context.title" in detail
    assert "{% macro detail_row" not in detail
    assert "{% macro detail_card" not in detail
    assert "{% macro technical_row" in shared
    assert "{% macro summary_metric" in shared


def test_node_inventory_registers_detail_and_technical_value_standards() -> None:
    technical = read("docs/design/components/TECHNICAL_VALUE.md")
    detail_styles = read("docs/design/components/DETAIL_STYLES.md")
    pattern = read("docs/design/patterns/INVENTORY_RESOURCE_PAGE.md")
    audit = read("docs/design/audits/KUBERNETES_NODE_INVENTORY_STYLING_AUDIT_2026_07.md")

    assert "normal proportional KAORI typography" in technical
    assert "monospace=true" in technical
    component = read("app/templates/components/technical_value.html")
    assert "monospace=false" in component
    assert "{% if monospace %}" in component
    assert "Detail Style 2 — Full Workspace Modal" in detail_styles
    assert "`full-workspace-modal`" in detail_styles
    assert "Kubernetes Node Inventory is the first canonical implementation" in pattern
    assert "Approved package" in audit


def test_pagination_component_supports_numeric_links_and_preserves_query_state() -> None:
    pagination = read("app/templates/components/pagination.html")

    assert "request.args.to_dict()" in pagination
    assert "window_start" in pagination
    assert "window_end" in pagination
    assert "hx_target=None" in pagination
