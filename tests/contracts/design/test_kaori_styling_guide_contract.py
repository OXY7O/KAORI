from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_canonical_styling_guide_and_component_contracts_exist() -> None:
    guide = _read('docs/design/KAORI_STYLING_GUIDE.md')
    design_readme = _read('docs/design/README.md')

    assert '# KAORI Styling Guide' in guide
    assert 'Non-Negotiable DRY Contract' in guide
    assert 'Font Hierarchy' in guide
    assert 'Hero Standard' in guide
    assert 'Pagination Standard' in guide
    assert 'Right-Side Context Boxes' in guide
    assert 'Label Standard' in guide
    assert 'View More Content' in guide
    assert 'Table Standard' in guide
    assert 'Workspace Catalog and Landing Pages' in guide
    assert 'KAORI_STYLING_GUIDE.md' in design_readme
    assert 'components/RIGHT_CONTEXT_RAIL.md' in design_readme
    assert 'components/VIEW_MORE_CONTENT.md' in design_readme
    assert 'components/WORKSPACE_LINK_CARD.md' in design_readme
    assert 'patterns/WELCOME_WORKSPACE_CATALOG.md' in design_readme
    assert 'components/WORKSPACE_TABS.md' in design_readme
    assert 'components/OPERATIONAL_SECTION_CARD.md' in design_readme
    assert 'components/FORECAST_PROJECTION_CHART.md' in design_readme
    assert 'components/ANALYTICS_OVERVIEW_SURFACES.md' in design_readme
    assert 'components/SECTION_HEADER_ACTION.md' in design_readme
    assert 'components/PEER_CONTENT_GRID.md' in design_readme
    assert 'components/OPERATIONAL_FLOW_STEPS.md' in design_readme
    assert 'components/OPERATIONAL_CALLOUT.md' in design_readme
    assert 'components/LOADING.md' in design_readme
    assert 'patterns/OPERATIONAL_DASHBOARD.md' in design_readme


def test_standard_labels_are_borderless_and_special_label_is_explicit() -> None:
    source = _read('app/templates/components/table_label.html')
    status = source.split('{% macro status_label', 1)[1].split('{%- endmacro %}', 1)[0]
    indicator = source.split('{% macro status_indicator_label', 1)[1].split('{%- endmacro %}', 1)[0]
    special = source.split('{% macro special_label', 1)[1].split('{%- endmacro %}', 1)[0]
    metadata = source.split('{% macro metadata_label', 1)[1].split('{%- endmacro %}', 1)[0]

    assert ' rounded-md ' in status
    assert ' border ' not in status
    assert ' rounded-full ' not in status
    assert ' rounded-md ' in indicator
    assert ' border ' not in indicator
    assert 'rounded-full' in indicator
    assert 'kaori-special-label' in special
    assert ' rounded-md border ' in special
    assert 'data-lucide="{{ icon }}"' in special
    assert ' border ' not in metadata


def test_right_context_rail_owns_the_standard_grid() -> None:
    source = _read('app/templates/components/context_rail.html')
    contract = _read('docs/design/components/RIGHT_CONTEXT_RAIL.md')

    assert 'xl:grid-cols-[minmax(0,1fr)_20rem]' in source
    assert 'space-y-4' in source
    assert 'components/context_rail.html' in contract
    assert 'Do not copy' in contract


def test_expandable_guidance_reuses_the_shared_view_more_shell() -> None:
    shared = _read('app/templates/components/view_more_content.html')
    information = _read('app/templates/components/information_guide_card.html')
    guidance = _read('app/templates/components/context_guidance_card.html')

    assert 'macro render' in shared
    assert 'View Details' in shared
    assert 'Collapse' in shared
    assert '{% import "components/view_more_content.html" as view_more_content %}' in information
    assert '{% call view_more_content.render(' in information
    assert '{% import "components/view_more_content.html" as view_more_content %}' in guidance
    assert '{% call view_more_content.render(' in guidance


def test_style_drift_verifier_matches_the_committed_baseline() -> None:
    module_path = ROOT / 'scripts' / 'verify_ui_style.py'
    spec = importlib.util.spec_from_file_location('verify_ui_style', module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    errors = module.validate(
        ROOT,
        ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json',
    )
    assert errors == []


def test_static_quality_gate_runs_the_style_drift_verifier() -> None:
    quality_gate = _read('scripts/quality_gate.sh')
    assert 'python scripts/verify_ui_reuse.py' in quality_gate
    assert 'python scripts/verify_ui_style.py' in quality_gate


def test_workspace_catalog_components_and_contracts_are_documented() -> None:
    card = _read('app/templates/components/workspace_link_card.html')
    group = _read('app/templates/components/welcome_capability_group.html')
    card_contract = _read('docs/design/components/WORKSPACE_LINK_CARD.md')
    catalog_contract = _read('docs/design/patterns/WELCOME_WORKSPACE_CATALOG.md')

    assert 'table_label.metadata_label(workspace.scope)' in card
    assert 'hover:-translate-y' not in card
    assert 'shadow-xl' not in card
    assert 'data-lucide="star"' not in group
    assert 'decorative rings' in catalog_contract
    assert 'components/workspace_link_card.html' in card_contract


def test_shared_empty_state_uses_canonical_label_macros() -> None:
    source = _read('app/templates/components/states/_empty_state.html')

    assert '{% import "components/table_label.html" as table_label %}' in source
    assert 'table_label.status_label(state_label, state_tone)' in source
    assert "table_label.special_label('Admin Required', 'unknown', 'shield')" in source
    assert 'text-[10px]' not in source


def test_style_verifier_tracks_compact_pill_label_drift() -> None:
    source = _read('scripts/verify_ui_style.py')

    assert "'page_local_compact_pill_labels'" in source
    assert "'arbitrary_tracking'" in source
    assert "'font_extrabold_utilities'" in source
    assert 'def _count_page_local_compact_pill_labels' in source


def test_operational_dashboard_components_and_contracts_are_documented() -> None:
    guide = _read('docs/design/KAORI_STYLING_GUIDE.md')
    section_card = _read('app/templates/components/operational_section_card.html')
    tabs = _read('app/templates/components/workspace_tabs.html')
    chart = _read('app/templates/components/forecast_projection_chart.html')
    info_flow = _read('app/templates/components/info_flow.html')

    assert 'Tab Style 1 — Integrated Workspace Tabs' in guide
    assert 'components/TAB_STYLES.md' in guide
    assert 'Dashboard metric typography' in guide
    assert 'Compact section-header action' in guide
    assert 'Forecast projection chart' in guide
    assert 'Primary and secondary flows' in guide
    assert 'components/peer_content_grid.html' in guide
    assert 'components/operational_flow_steps.html' in guide
    assert 'components/operational_callout.html' in guide
    assert 'text-base font-semibold' in section_card
    assert 'role="tablist"' in tabs
    assert 'rounded-xl' not in tabs
    assert 'border-b border-outline-subtle' in tabs
    assert '<svg' in chart
    assert '<details' not in info_flow


def test_tab_style_registry_names_the_integrated_workspace_pattern() -> None:
    registry = _read('docs/design/components/TAB_STYLES.md')
    contract = _read('docs/design/components/WORKSPACE_TABS.md')
    tabs = _read('app/templates/components/workspace_tabs.html')
    design_readme = _read('docs/design/README.md')

    assert 'Tab Style 1 — Integrated Workspace Tabs' in registry
    assert '`integrated-workspace`' in registry
    assert 'Kubernetes Operations Dashboard' in registry
    assert 'visual variation alone' in registry or 'Color, radius, spacing' in registry
    assert 'Review name: **Tab Style 1**' in contract
    assert 'data-kaori-tab-variant="integrated-workspace"' in tabs
    assert 'components/TAB_STYLES.md' in design_readme


def test_style_verifier_tracks_page_local_workspace_tablists() -> None:
    source = _read('scripts/verify_ui_style.py')

    assert "'page_local_workspace_tablists'" in source
    assert '_TABLIST = re.compile' in source
    assert "'app/templates/components/forecast_projection_chart.html'" in source


def test_peer_content_grid_is_distinct_from_the_context_rail() -> None:
    grid = _read('app/templates/components/peer_content_grid.html')
    grid_contract = _read('docs/design/components/PEER_CONTENT_GRID.md')
    rail_contract = _read('docs/design/components/RIGHT_CONTEXT_RAIL.md')

    assert 'xl:grid-cols-12' in grid
    assert 'xl:col-span-6' in grid
    assert 'seven-five' in grid
    assert 'both columns are primary page content' in grid_contract
    assert 'supporting context' in grid_contract
    assert 'supporting information' in rail_contract
    assert 'tallest peer block' in grid_contract


def test_operational_callout_owns_semantic_border_variants() -> None:
    component = _read('app/templates/components/operational_callout.html')
    verifier = _read('scripts/verify_ui_style.py')
    contract = _read('docs/design/components/OPERATIONAL_CALLOUT.md')

    assert 'border-status-critical-border' in component
    assert "variant == 'semantic'" in component
    assert "'app/templates/components/operational_callout.html'" in verifier
    assert 'not a compact status label' in contract


def test_inventory_overview_components_and_pattern_are_documented() -> None:
    guide = _read('docs/design/KAORI_STYLING_GUIDE.md')
    design_readme = _read('docs/design/README.md')
    snapshot = _read('app/templates/components/snapshot_context_bar.html')
    asset_card = _read('app/templates/components/inventory_asset_card.html')
    drawer = _read('app/templates/components/side_drawer.html')
    pattern = _read('docs/design/patterns/KUBERNETES_INVENTORY_OVERVIEW.md')

    assert 'Snapshot context bar' in guide
    assert 'Inventory asset card' in guide
    assert 'Right-side detail drawer' in guide
    assert 'Compact cluster inventory table' in guide
    assert 'components/SNAPSHOT_CONTEXT_BAR.md' in design_readme
    assert 'components/INVENTORY_ASSET_CARD.md' in design_readme
    assert 'components/SIDE_DRAWER.md' in design_readme
    assert 'patterns/KUBERNETES_INVENTORY_OVERVIEW.md' in design_readme
    assert 'table_label.status_label' in snapshot
    assert '>Source:</span>' in snapshot
    assert 'Snapshot Exceptions' in snapshot
    assert 'xl:col-span-4' in snapshot
    assert 'xl:col-span-8' in snapshot
    assert 'xl:grid-cols-4' in snapshot
    assert 'Open Inventory' in asset_card
    assert 'role="dialog"' in drawer
    assert '{% macro section(' in drawer
    assert '{% macro metric(' in drawer
    assert 'Operational Context' in pattern
    assert 'The hero does not show last sync' in pattern
    assert 'Cluster | Connection | Total Objects | Last Snapshot | Inventory Signals | Details' in pattern


def test_visualization_workspace_and_tab_style_two_are_documented() -> None:
    guide = _read('docs/design/KAORI_STYLING_GUIDE.md')
    design_readme = _read('docs/design/README.md')
    registry = _read('docs/design/components/TAB_STYLES.md')
    visualization = _read('docs/design/components/VISUALIZATION_WORKSPACE.md')
    segmented = _read('docs/design/components/SEGMENTED_TABS.md')
    palette = _read('docs/design/components/TOPOLOGY_PALETTE.md')

    assert 'Tab Style 2 — Compact Segmented Tabs' in guide
    assert 'Visualization Workspace Style 1 — Adaptive Explorer' in guide
    assert 'components/SEGMENTED_TABS.md' in design_readme
    assert 'components/VISUALIZATION_WORKSPACE.md' in design_readme
    assert 'components/TOPOLOGY_PALETTE.md' in design_readme
    assert 'patterns/KUBERNETES_TOPOLOGY.md' in design_readme
    assert 'Tab Style 2 — Compact Segmented Tabs' in registry
    assert '`compact-segmented`' in registry
    assert 'adaptive-explorer' in visualization
    assert 'Resource List' in visualization
    assert 'Left/Right/Home/End' in segmented
    assert 'five-domain palette' in palette


def test_visualization_workspace_is_an_approved_shared_surface_owner() -> None:
    verifier = _read('scripts/verify_ui_style.py')
    component = _read('app/templates/components/visualization_workspace.html')

    assert "'app/templates/components/visualization_workspace.html'" in verifier
    assert 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm' in component


def test_namespace_inventory_and_technical_metadata_are_documented() -> None:
    guide = _read("docs/design/KAORI_STYLING_GUIDE.md")
    component = _read("docs/design/components/TECHNICAL_METADATA_COLLECTION.md")
    pattern = _read("docs/design/patterns/KUBERNETES_NAMESPACE_INVENTORY.md")

    assert "Namespace Inventory and Technical Metadata" in guide
    assert "Missing ResourceQuota" in guide
    assert "technical_metadata_collection.html" in guide
    assert "Technical Metadata Collection" in component
    assert "No Implicit Compliance" not in pattern
    assert "explicit governance policy" in pattern


def test_adaptive_detail_density_and_page_size_ownership_are_documented() -> None:
    guide = _read('docs/design/KAORI_STYLING_GUIDE.md')
    detail_contract = _read('docs/design/components/DETAIL_STYLES.md')
    shared_detail = _read('app/templates/components/details/_detail_content.html')

    assert 'Adaptive Detail Stacks' in guide
    assert 'Page-Size Ownership' in guide
    assert 'data-kaori-detail-density="adaptive-stacks"' in detail_contract
    assert 'stretch=false' in detail_contract
    assert 'detail.evidence_grid(...)' in detail_contract
    assert 'macro evidence_grid' in shared_detail
    assert "{{ 'h-full' if stretch else '' }}" in shared_detail


def test_pod_runtime_components_and_pattern_are_documented() -> None:
    guide = _read('docs/design/KAORI_STYLING_GUIDE.md')
    design_readme = _read('docs/design/README.md')
    runtime_contract = _read('docs/design/components/CONTAINER_RUNTIME_COLLECTION.md')
    pod_pattern = _read('docs/design/patterns/KUBERNETES_POD_INVENTORY.md')
    runtime_component = _read('app/templates/components/container_runtime_collection.html')
    related_component = _read('app/templates/components/related_resource_collection.html')

    assert 'Pod Runtime and Container Evidence' in guide
    assert 'Ready, Starting, Not Ready, Failed, Completed, and Unknown' in guide
    assert 'components/CONTAINER_RUNTIME_COLLECTION.md' in design_readme
    assert 'patterns/KUBERNETES_POD_INVENTORY.md' in design_readme
    assert 'terminated exit code `0` is Completed' in runtime_contract
    assert 'Pod | Scope | Runtime State | Placement | Ownership & Activity | Details' in pod_pattern
    assert 'table_label.status_indicator_label(container.runtime_state_label' in runtime_component
    assert '{% if resource.status %}' in related_component


def test_network_inventory_pattern_is_registered() -> None:
    guide = (ROOT / 'docs/design/KAORI_STYLING_GUIDE.md').read_text(encoding='utf-8')
    pattern = (ROOT / 'docs/design/patterns/KUBERNETES_NETWORK_INVENTORY.md').read_text(encoding='utf-8')

    assert 'Service and Ingress Network Inventory' in guide
    assert 'EndpointSlice first' in guide
    assert 'No TLS reference remains neutral inventory evidence' in guide
    assert 'Kubernetes Network Inventory Pattern' in pattern



def test_analytics_overview_surface_hierarchy_is_documented_and_shared() -> None:
    guide = _read('docs/design/KAORI_STYLING_GUIDE.md')
    contract = _read('docs/design/components/ANALYTICS_OVERVIEW_SURFACES.md')
    shared = _read('app/templates/analytics/components/_overview_surfaces.html')
    hero = _read('app/templates/components/page_hero.html')
    labels = _read('app/templates/components/table_label.html')

    assert 'Analytics Overview Surface Hierarchy' in guide
    assert 'analytics/components/_overview_surfaces.html' in guide
    assert 'Primary Data Surface' in contract
    assert 'Interpretation or Action Strip' in contract
    assert 'Attention Strip' in contract
    assert 'macro readiness_shell_classes' in shared
    assert 'macro interpretation_grid_classes' in shared
    assert 'macro context_panel_classes' in shared
    assert 'macro context_bottom_notice' in hero
    assert "'green'" in labels
    assert "'amber'" in labels
    assert "'red'" in labels
    assert "'gray'" in labels
