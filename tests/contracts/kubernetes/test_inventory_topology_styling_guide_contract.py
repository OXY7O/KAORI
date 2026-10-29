from __future__ import annotations

import json
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_topology_uses_the_adaptive_visualization_workspace() -> None:
    workspace = _read('app/templates/kubernetes/inventory/topology/partials/_workspace.html')
    component = _read('app/templates/components/visualization_workspace.html')
    script = _read('app/static/js/kubernetes/inventory/topology.js')

    assert '{% import "components/visualization_workspace.html" as visualization_workspace %}' in workspace
    assert 'visualization_workspace.render(' in workspace
    assert 'data-kaori-visualization-workspace="adaptive-explorer"' in component
    assert 'relative min-h-[38rem]' in component
    assert '2xl:grid-cols-' not in component
    assert '2xl:static' not in component
    assert '2xl:block' not in component
    assert 'topology-controls-panel' in workspace
    assert 'topology-details-panel' in workspace
    assert 'topology-pane-backdrop' in workspace
    assert 'topology-controls-button' in workspace
    assert 'topology-details-button' in workspace
    assert '2xl:hidden' not in workspace
    assert 'components/loading_bar.html' in component
    assert 'data-kaori-visualization-header-actions' in component
    assert "action_label='Reload Snapshot'" in workspace
    assert 'action_classes=table_ui.action_classes()' in workspace
    assert "action_classes=''" in component
    assert 'topology-clear-filters-button' in workspace
    assert 'hidden=not topology_filters_active' in workspace
    assert 'clearFiltersButton.hidden = !hasActiveFilters()' in script
    assert 'placeholder="Search resources"' in workspace
    assert 'Search and open a resource in the current topology scope.' not in workspace
    assert 'topology-search-summary' not in workspace
    assert 'searchSummary' not in script


def test_topology_side_panes_are_always_on_demand_drawers() -> None:
    workspace = _read('app/templates/kubernetes/inventory/topology/partials/_workspace.html')
    component = _read('app/templates/components/visualization_workspace.html')
    script = _read('app/static/js/kubernetes/inventory/topology.js')
    pattern = _read('docs/design/patterns/KUBERNETES_TOPOLOGY.md')

    assert 'fixed inset-y-0' in component
    assert 'z-50 hidden w-full' in component
    assert "'left-0 border-r max-w-sm' if side == 'left'" in component
    assert "'right-0 border-l max-w-2xl'" in component
    assert '2xl:static' not in component
    assert 'isPersistentExplorer' not in script
    assert 'if (!panel) return' in script
    assert 'openPane(detailsPanel)' in script
    assert 'data-topology-close-pane' in workspace
    assert 'overlay drawers at every breakpoint' in pattern.lower()
    assert 'never become persistent' in pattern.lower()


def test_topology_registers_compact_segmented_tab_style() -> None:
    workspace = _read('app/templates/kubernetes/inventory/topology/partials/_workspace.html')
    inspector = _read('app/templates/kubernetes/inventory/topology/partials/_inspector_templates.html')
    component = _read('app/templates/components/segmented_tabs.html')
    script = _read('app/static/js/kubernetes/inventory/topology.js')
    registry = _read('docs/design/components/TAB_STYLES.md')

    assert 'Tab Style 3 — Compact Segmented Tabs' in registry
    assert '`compact-segmented`' in registry
    assert 'data-kaori-tab-variant="compact-segmented"' in component
    assert 'data-kaori-segmented-group="{{ prefix }}"' in component
    assert 'data-kaori-segmented-tab="{{ tab_key }}"' in component
    assert 'data_attribute' not in component
    assert "('graph', 'Graph', 'share-2')" in workspace
    assert "('list', 'Resource List', 'list-tree')" in workspace
    assert "('details', 'Details', 'list-tree')" in inspector
    assert "('relationships', 'Relationships', 'git-branch')" in inspector
    assert 'fill=true' in inspector
    assert 'fill=true' not in workspace
    assert "{{ 'flex w-full' if fill else 'inline-flex' }}" in component
    assert "{{ 'min-w-0 flex-1' if fill else '' }}" in component
    assert 'data-kaori-segmented-group="topology-view"' in script
    assert 'data-kaori-segmented-group="topology-inspector"' in script
    assert 'dataset.kaoriSegmentedTab' in script
    assert 'dataset.topologyViewTab' not in script
    assert 'dataset.topologyNodeTab' not in script
    assert 'role="tablist"' not in workspace
    assert 'role="tablist"' not in inspector


def test_compact_segmented_tabs_render_stable_controller_hooks() -> None:
    environment = Environment(loader=FileSystemLoader(ROOT / 'app/templates'))
    component = environment.get_template('components/segmented_tabs.html').module

    rendered = component.render(
        [('details', 'Details', 'list-tree'), ('relationships', 'Relationships', 'git-branch')],
        prefix='topology-inspector',
        active_key='details',
        aria_label='Topology Inspector',
    )

    assert 'data-kaori-segmented-group="topology-inspector"' in rendered
    assert 'data-kaori-segmented-tab="details"' in rendered
    assert 'data-kaori-segmented-tab="relationships"' in rendered
    assert 'aria-selected="true"' in rendered
    assert 'None=' not in rendered


def test_compact_segmented_tabs_support_symmetric_bounded_inspectors() -> None:
    environment = Environment(loader=FileSystemLoader(ROOT / 'app/templates'))
    component = environment.get_template('components/segmented_tabs.html').module

    rendered = component.render(
        [('details', 'Details', 'list-tree'), ('relationships', 'Relationships', 'git-branch')],
        prefix='topology-inspector',
        active_key='details',
        aria_label='Topology Inspector',
        fill=True,
    )

    assert 'flex w-full' in rendered
    assert rendered.count('min-w-0 flex-1') == 2
    assert 'data-kaori-segmented-tab="details"' in rendered
    assert 'data-kaori-segmented-tab="relationships"' in rendered


def test_topology_graph_has_an_accessible_resource_list_fallback() -> None:
    workspace = _read('app/templates/kubernetes/inventory/topology/partials/_workspace.html')
    script = _read('app/static/js/kubernetes/inventory/topology.js')
    index = _read('app/templates/kubernetes/inventory/topology/index.html')

    assert 'role="application"' not in workspace
    assert 'role="img"' in workspace
    assert 'topology-view-panel-list' in workspace
    assert 'topology-resource-list-body' in workspace
    assert 'role="combobox"' in workspace
    assert 'role="listbox"' in workspace
    assert "event.key === 'ArrowDown'" in script
    assert "event.key === 'ArrowUp'" in script
    assert "event.key === 'Enter'" in script
    assert 'Resource List remains available from the committed inventory snapshot.' in script
    assert 'renderPayloadNodeDetails' in script
    assert "setActiveView('list')" in script
    assert "filename='js/kubernetes/inventory/topology.js'" in index
    assert "'renderer_url':" in index
    assert "'workspace_url':" not in index
    assert 'await import(config.renderer_url)' in script
    assert 'Topology renderer could not start:' in script
    assert not (ROOT / 'app/static/js/inventory/topology_bootstrap.js').exists()


def test_topology_inspector_uses_native_templates_instead_of_tailwind_html_strings() -> None:
    workspace = _read('app/templates/kubernetes/inventory/topology/partials/_workspace.html')
    inspector = _read('app/templates/kubernetes/inventory/topology/partials/_inspector_templates.html')
    script = _read('app/static/js/kubernetes/inventory/topology.js')

    assert '_inspector_templates.html' in workspace
    assert 'topology-node-inspector-template' in inspector
    assert 'topology-edge-inspector-template' in inspector
    assert 'topology-resource-list-row-template' in inspector
    assert 'cloneTemplate' in script
    assert 'detailContent.innerHTML' not in script
    assert 'searchResults.innerHTML' not in script


def test_topology_palette_is_tokenized_and_contains_no_raw_js_colors() -> None:
    styles = _read('frontend/styles.css')
    script = _read('app/static/js/kubernetes/inventory/topology.js')
    contract = _read('docs/design/components/TOPOLOGY_PALETTE.md')

    for domain in ('scope', 'compute', 'networking', 'configuration', 'storage'):
        assert f'--kaori-topology-domain-{domain}-fill' in styles
        assert f'--kaori-topology-domain-{domain}-border' in styles
        assert f'--kaori-topology-domain-{domain}-text' in styles
        assert f'.kaori-topology-domain-{domain}' in styles
        assert f'background-color: var(--kaori-topology-domain-{domain}-fill);' in styles
        assert f'border-color: var(--kaori-topology-domain-{domain}-border);' in styles
        assert f'color: var(--kaori-topology-domain-{domain}-text);' in styles
    for relationship in ('contains', 'owns', 'scheduled', 'selects', 'routes', 'uses', 'mounts', 'binds'):
        assert f'--kaori-topology-edge-{relationship}' in styles
    assert re.search(r'(?<![\w-])#[0-9a-fA-F]{3,8}\b', script) is None
    assert 'five-domain palette' in contract
    assert "shape: 'round-rectangle'" in script
    assert "'text-wrap': 'ellipsis'" in script
    assert "'text-valign': 'bottom'" in script
    assert "'text-max-width': 220" in script
    assert 'nodeBadgeSvg' in script
    assert 'data.display_label = data.base_label' in script
    assert 'selector: \'edge[relationship = "contains"]\'' in script
    assert "'target-arrow-shape': 'none'" in script
    assert 'External Label Node' in contract


def test_topology_hero_does_not_duplicate_snapshot_context() -> None:
    hero = _read('app/templates/kubernetes/inventory/topology/partials/_hero.html')

    assert 'Graph Coverage' in hero
    assert 'Relationships' in hero
    assert 'Last Collected' not in hero
    assert 'Inventory Database Snapshot' not in hero


def test_topology_service_bounds_queries_and_caches_committed_payloads() -> None:
    service = _read('app/kubernetes/inventory/topology/service.py')
    repository = _read('app/kubernetes/inventory/topology/repository.py')
    node_builder = _read('app/kubernetes/inventory/topology/node_builder.py')
    edge_builder = _read('app/kubernetes/inventory/topology/edge_builder.py')
    presentation = _read('app/kubernetes/inventory/topology/presentation.py')

    assert '_TOPOLOGY_CACHE_MAX_ENTRIES' in service
    assert '_topology_cache_get' in service
    assert '_topology_cache_put' in service
    assert '_TOPOLOGY_CACHE_LOCK' in service
    assert 'generation_signature' in service
    assert 'filter_current_generation' in repository
    assert 'if not selection.include_level_2 or not selection.show_networking' in repository
    assert 'if not selection.include_level_2 or not selection.show_configuration' in repository
    assert 'if not selection.include_level_2 or not selection.show_storage' in repository
    assert 'services_by_scope' in node_builder
    assert 'pods_by_scope' in edge_builder
    assert 'omitted_by_type' in presentation
    assert '_node_element' not in service
    assert 'class TopologyGraphBuilder' in _read('app/kubernetes/inventory/topology/graph_builder.py')


def test_topology_reference_pattern_is_documented() -> None:
    pattern = _read('docs/design/patterns/KUBERNETES_TOPOLOGY.md')
    audit = _read('docs/design/audits/KUBERNETES_TOPOLOGY_STYLING_AUDIT_2026_07.md')
    inventory_readme = _read('app/kubernetes/inventory/README.md')

    assert 'Visualization Workspace Style 1 — Adaptive Explorer' in pattern
    assert 'Tab Style 3: Graph / Resource List' in pattern
    assert (
        'Renderer failure must not remove access' in pattern
        or 'Renderer errors preserve Resource List access' in pattern
    )
    assert 'Approved package' in audit
    assert 'Kubernetes Topology Reference Pattern' in inventory_readme


def test_topology_cluster_icon_and_api_server_layout_are_readable() -> None:
    inspector = _read('app/templates/kubernetes/inventory/topology/partials/_inspector_templates.html')
    script = _read('app/static/js/kubernetes/inventory/topology.js')

    assert "cluster: { icon: 'server', domain: 'scope' }" in script
    assert "cluster: { icon: 'server-cog', domain: 'scope' }" not in script
    assert 'topology-stacked-field-row-template' not in inspector
    assert "normalizedLabel === 'api server'" in script
    assert "valueElement.classList.add('min-w-0', 'flex-1', 'truncate', 'whitespace-nowrap')" in script
    assert "valueElement.title = String(displayValue || 'Not Reported')" in script
    assert 'topology_parts.field_row_template("topology-field-row-template")' in inspector
    assert 'max-w-[28rem]' in _read('app/templates/components/topology_primitives.html')
    assert 'max-w-2xl' in _read('app/templates/components/visualization_workspace.html')


def test_topology_runtime_status_strips_use_shared_semantic_border_authority() -> None:
    workspace_path = 'app/templates/kubernetes/inventory/topology/partials/_workspace.html'
    workspace = _read(workspace_path)
    baseline = json.loads(_read('docs/architecture/ui-style-debt-baseline.json'))

    assert 'components/table_label.html' in workspace
    assert "table_label.tone_border_classes('warning')" in workspace
    assert "table_label.tone_border_classes('critical')" in workspace
    assert "table_label.tone_border_classes('pending')" in workspace

    for direct_border in (
        'border-status-warning-border',
        'border-status-critical-border',
        'border-status-pending-border',
    ):
        assert direct_border not in workspace

    assert 'id="topology-limit-warning"' in workspace
    assert 'id="topology-error"' in workspace
    assert 'role="alert"' in workspace
    assert 'id="topology-runtime-status"' in workspace
    assert 'role="status"' in workspace
    assert workspace_path not in baseline['files']


def test_topology_hover_only_relationship_labels_and_legend() -> None:
    script = _read('app/static/js/kubernetes/inventory/topology.js')
    workspace = _read('app/templates/kubernetes/inventory/topology/partials/_workspace.html')
    palette = _read('docs/design/components/TOPOLOGY_PALETTE.md')

    # Relationship labels stay hidden by default, including on small graphs.
    assert "if (workspaceState.edgeLabels) cy.edges(':visible').addClass('edge-label-visible')" in script
    assert 'smallGraph' not in script
    assert 'visibleEdges.length <= 8' not in script
    assert "cy.edges('.edge-hovered:visible').addClass('edge-label-visible')" in script
    assert "cy.edges(':selected:visible').addClass('edge-label-visible')" in script
    assert "cy.edges('.path-active:visible').addClass('edge-label-visible')" in script
    # Only the hovered edge gains a label and emphasis; mouseout restores persistent states.
    assert "cy.on('mouseover', 'edge', (event) => {" in script
    assert "event.target.addClass('edge-hovered edge-label-visible')" in script
    assert "cy.on('mouseout', 'edge', (event) => {" in script
    assert "event.target.removeClass('edge-hovered')" in script
    assert 'updateEdgeLabelClasses()' in script
    assert "selector: 'edge.edge-hovered'" in script
    assert "'line-color': brandPrimary" in script
    assert "cy.on('mouseover', 'node'" not in script
    # Retain the existing semantic label chip and explicit opt-in control.
    assert "'text-background-shape': 'roundrectangle'" in script
    assert "'text-rotation': 'none'" in script
    assert 'selector: \'edge[relationship = "contains"].edge-label-visible\'' in script
    assert "style: { 'text-margin-y': 24 }" in script
    assert 'Always Show Relationship Labels' in workspace
    assert 'Dashed: scope · Arrows: operational' in workspace
    assert 'mt-2 whitespace-nowrap text-xs leading-5 text-content-muted' in workspace
    assert (
        'title="Dashed lines show scope containment; solid arrows show directional operational relationships.'
        in workspace
    )
    assert (
        'aria-label="Dashed lines show scope containment; solid arrows show directional operational relationships.'
        in workspace
    )
    assert 'Relationship legend: dashed lines show scope containment' not in workspace
    assert 'Hover or select an edge to reveal its label' in workspace
    assert 'Relationship labels stay hidden by default' in palette


def test_topology_compact_layout_fits_external_labels_and_resize() -> None:
    script = _read('app/static/js/kubernetes/inventory/topology.js')
    pattern = _read('docs/design/patterns/KUBERNETES_TOPOLOGY.md')

    assert "const visibleCount = cy ? cy.nodes(':visible').length : 0" in script
    assert 'spacingFactor: visibleCount <= 8 ? 1.18 : visibleCount <= 35 ? 1.13 : 1.24' in script
    assert 'visible.boundingBox({ includeLabels: true, includeOverlays: false })' in script
    assert 'cy.fit(bounds, padding)' in script
    assert 'cy.center(visible)' not in script
    assert "if (!cy || activeView !== 'graph') return" in script
    assert 'visible.renderedBoundingBox({ includeLabels: true, includeOverlays: false })' in script
    assert 'window.requestAnimationFrame(fitGraphToCanvas)' in script
    assert '## Compact Hierarchy and Viewport Safety' in pattern
    assert 'Dependency View remains independent' in pattern


def test_topology_relationship_summary_reuses_existing_inspector() -> None:
    inspector = _read('app/templates/kubernetes/inventory/topology/partials/_inspector_templates.html')
    script = _read('app/static/js/kubernetes/inventory/topology.js')
    pattern = _read('docs/design/patterns/KUBERNETES_TOPOLOGY.md')

    assert 'data-node-relationship-summary' in inspector
    assert 'topology-relationship-summary-item-template' in inspector
    assert 'data-open-relationships' in inspector
    assert 'role="list"' in inspector
    assert 'aria-label="View all visible relationships for this resource"' in inspector
    assert "const edges = node.connectedEdges(':visible')" in script
    assert 'const renderRelationshipSummary = (view, node) =>' in script
    assert 'renderRelationshipSummary(view, node)' in script
    assert "activateTab('relationships')" in script
    assert 'edgeColor(relationship)' in script
    assert 'Relationship Summary' in pattern
    assert "selector: 'edge.focused'" in script
    assert 'edge.focused[relationship' in script
    assert "const resourceCount = nodes.filter((node) => node.data('type') !== 'namespace').length" in script
    assert 'if (!resourceCount) return' in script
    assert 'Namespace boundary overlays appear only' in pattern
    assert 'visible committed edge type and direction' in pattern


def test_topology_regular_external_labels_and_semantic_operational_arrows() -> None:
    script = _read('app/static/js/kubernetes/inventory/topology.js')
    workspace = _read('app/templates/kubernetes/inventory/topology/partials/_workspace.html')
    edge_builder = _read('app/kubernetes/inventory/topology/edge_builder.py')
    palette = _read('docs/design/components/TOPOLOGY_PALETTE.md')

    # External resource labels are regular; glyphs inside the badge still identify node type.
    assert "'font-size': 10,\n                    'font-weight': 400" in script
    assert "'font-size': 11, 'font-weight': 400" in script
    assert 'font-weight="700"' in script
    assert "'font-size': 9,\n                    'font-weight': 500" in script

    # Subtle operational paths remain directional and distinct from containment.
    assert 'selector: \'edge[relationship = "owns"]\'' in script
    assert "style: { 'line-opacity': 0.74, 'arrow-scale': 0.66, width: 1.7 }" in script
    assert 'selector: \'edge[relationship = "scheduled_on"]\'' in script
    assert "style: { 'line-opacity': 0.58, 'arrow-scale': 0.58, width: 1.35 }" in script
    assert 'selector: \'edge[relationship = "contains"]\'' in script
    assert "'target-arrow-shape': 'none'" in script
    assert "'target-arrow-shape': 'triangle'" in script
    assert "relationship='owns'" in edge_builder
    assert "relationship='scheduled_on'" in edge_builder
    assert "('owns', 'Owns', 'owns')" in workspace
    assert "('scheduled_on', 'Scheduled on', 'scheduled')" in workspace
    assert 'Dashed: scope · Arrows: operational' in workspace
    assert '## Readable Label and Operational Edge Hierarchy' in palette

    # Intentional interaction emphasis and previously approved hover behavior stay intact.
    assert "selector: 'edge.edge-hovered'" in script
    assert "cy.edges(':selected:visible').addClass('edge-label-visible')" in script
    assert "'text-margin-y': 24" in script
    assert 'Always Show Relationship Labels' in workspace
