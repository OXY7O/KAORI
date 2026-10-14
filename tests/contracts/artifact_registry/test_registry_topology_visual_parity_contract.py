"""Artifact Registry topology must reuse canonical Kubernetes visual grammar (#1692).

Source-level guard only; live DevContainer visual UAT remains mandatory.
"""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / 'app/templates/artifact_registry/topology.html'
RUNTIME_JS = ROOT / 'app/static/js/artifact_registry/topology.js'
K8S = ROOT / 'app/templates/kubernetes/inventory/topology/partials/_workspace.html'
PALETTE = ROOT / 'docs/design/components/TOPOLOGY_PALETTE.md'


def test_registry_topology_reuses_kubernetes_canvas_first_shell() -> None:
    registry = REGISTRY.read_text(encoding='utf-8')
    kubernetes = K8S.read_text(encoding='utf-8')
    Environment().parse(registry)
    Environment().parse(kubernetes)

    for shared in (
        'visualization.canvas_classes()',
        'visualization.adaptive_grid_classes()',
        "visualization.drawer_pane_classes('left')",
        "visualization.drawer_pane_classes('right')",
    ):
        assert shared in registry
        assert shared.replace('visualization.', 'visualization_workspace.') in kubernetes

    assert 'segmented_tabs.render(' in registry
    assert 'segmented_tabs.render(' in kubernetes
    assert "prefix='registry-topology-view'" in registry
    assert "('graph', 'Graph', 'share-2')" in registry
    assert "('list', 'Resource List', 'list-tree')" in registry

    for element in (
        'registry-topology-controls-button',
        'registry-topology-details-button',
        'registry-topology-controls-close',
        'registry-topology-inspector-close',
        'registry-topology-backdrop',
        'registry-topology-fit',
        'registry-topology-reset',
        'registry-topology-export',
        'registry-topology-export-json',
        'registry-topology-view-panel-graph',
        'registry-topology-view-panel-list',
        'registry-topology-node-tooltip',
    ):
        assert f'id="{element}"' in registry

    assert 'role="img"' in registry
    assert 'role="tabpanel"' in registry
    assert 'aria-modal="true"' in registry
    assert 'data-registry-topology-type' in registry
    assert 'data-registry-topology-relationship' in registry
    assert 'components/states/_empty_state.html' in registry


def test_registry_renderer_adopts_kubernetes_graph_semantics() -> None:
    renderer = RUNTIME_JS.read_text(encoding='utf-8')
    canonical = (ROOT / 'app/static/js/kubernetes/inventory/topology.js').read_text(encoding='utf-8')
    for phrase in (
        "'background-image'",
        "'text-margin-y': 11",
        "'text-valign': 'bottom'",
        "'text-background-opacity'",
        "'background-image-containment': 'inside'",
        "'text-wrap': 'ellipsis'",
        'nodeDimensionsIncludeLabels: true',
        'includeLabels: true',
        "name: 'breadthfirst'",
        "name: 'cose'",
    ):
        assert phrase in renderer
        assert phrase in canonical

    assert 'width: 76' in renderer
    assert 'height: 44' in renderer
    assert 'badgeImage(node.data())' in renderer
    assert 'transform: (_node, position) => (branched ? position : { x: position.y, y: position.x })' in renderer
    assert "'line-style': (edge) => edge.data('relationship') === 'contains'" in renderer
    assert 'selector: \'edge[relationship = "contains"]\'' in renderer
    assert "'curve-style': 'taxi'" in renderer
    assert "'taxi-direction': 'horizontal'" in renderer
    assert "selector: 'edge.edge-label-visible'" in renderer
    assert "selector: 'edge.edge-hovered'" in renderer
    assert "cy.on('mouseover', 'edge'" in renderer
    assert "cy.on('mouseout', 'edge'" in renderer
    assert 'updateEdgeLabelClasses()' in renderer
    assert "'kaori-topology-muted'" in renderer
    assert 'graphHasLayout' in renderer
    assert 'aria-selected' in renderer
    assert 'closePane()' in renderer
    assert 'scopeSummary.textContent' in renderer
    assert 'summary.omitted_bindings' in renderer
    assert "evidence.status !== 'ready'" in renderer
    assert 'URL.createObjectURL(new Blob(' in renderer
    assert 'canvas.dataset.rendererUrl' in renderer
    assert not re.search(r'#[0-9A-Fa-f]{3,8}\b', renderer)

    palette = PALETTE.read_text(encoding='utf-8')
    assert 'External Label Node' in palette
    assert 'raw hex' in palette.lower()
    assert 'kaori-topology-domain-configuration' in REGISTRY.read_text(encoding='utf-8')


def test_visual_refactor_does_not_move_registry_evidence_authority() -> None:
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text(encoding='utf-8')
    projection = (ROOT / 'app/artifact_registry/presentation_topology.py').read_text(encoding='utf-8')
    assert 'build_dependency_topology(**_runtime_topology_filters())' in routes
    assert "@permission_required('artifact_registry.view')" in routes
    assert 'RegistryWorkloadBinding' in projection
    assert '.limit(_MAX_VISIBLE_BINDINGS)' in projection
    assert 'runtime_correlation_evidence_readiness' in projection


def test_registry_inspector_matches_k8s_details_and_relationships_design() -> None:
    registry = REGISTRY.read_text(encoding='utf-8')
    partial_path = ROOT / 'app/templates/artifact_registry/partials/_topology_inspector_templates.html'
    inspector = partial_path.read_text(encoding='utf-8')
    renderer = RUNTIME_JS.read_text(encoding='utf-8')
    Environment().parse(inspector)
    assert 'artifact_registry/partials/_topology_inspector_templates.html' in registry
    assert 'segmented_tabs.render(' in inspector
    assert "('details', 'Details', 'list-tree')" in inspector
    assert "('relationships', 'Relationships', 'git-branch')" in inspector
    for control in (
        'data-highlight-path',
        'data-collapse-path',
        'data-relationship-summary',
        'data-open-relationships',
        'data-node-relationships',
        'data-minimap',
        'data-node-status',
        'registry-topology-resource-list-row-template',
        'registry-topology-inspector-relationship-row-template',
    ):
        assert control in inspector
    for behavior in (
        'const renderRelationshipRows =',
        'const drawMiniMap =',
        'const selectNodeById =',
        'const inspect =',
        'const graphParents =',
        'const resourceScope =',
        'const renderList =',
        'collapseNodeIds',
    ):
        if behavior == 'collapseNodeIds':
            assert 'collapsedNodeIds' in renderer
        else:
            assert behavior in renderer
    assert "node.connectedEdges(':visible')" in renderer
    assert "pane.querySelector('[data-relationship-summary]')" in renderer
    assert "node.predecessors('node')" in renderer
    assert 'scheduleDrawerMiniMapUpdate()' in renderer
    assert 'const scope = resourceScope(item, parents, byId)' in renderer
    assert 'payload.nodes.filter(' in renderer
    assert 'resourceToggles' in renderer
    assert 'relationshipToggles' in renderer
    assert 'groupNamespaceToggle' in renderer
    assert 'updateNamespaceBoundaries' in renderer
    assert "evidence.status !== 'ready'" in renderer


def test_registry_topology_auto_filters_use_canonical_header_actions_and_loading() -> None:
    template = REGISTRY.read_text(encoding='utf-8')
    renderer = RUNTIME_JS.read_text(encoding='utf-8')
    Environment().parse(template)
    assert 'components/table_registry.html' in template
    assert 'registry_ui.clear_filters_action(' in template
    assert "id='registry-topology-clear-filters'" in template
    assert 'header_actions=registry_topology_header_actions' in template
    assert 'id="registry-topology-clear-filters"' not in template  # macro owns the control
    assert 'Apply Filters' not in template
    assert 'lg:grid-cols-6' in template
    assert "loading_id='registry-topology-loading'" in template
    assert "const loading = $('registry-topology-loading')" in renderer
    assert "loading?.classList.toggle('htmx-request', state)" in renderer
    assert 'const setLoading = (state) =>' in renderer
    assert 'if (controller === requestController) setLoading(false)' in renderer
    assert 'const requestController = new AbortController()' in renderer
    assert "select.addEventListener('change', commitFilterChange)" in renderer
    assert 'searchTimer = window.setTimeout(commitFilterChange, 350)' in renderer
    assert "clearFiltersButton?.addEventListener('click'" in renderer
    assert 'form.querySelector(\'input[name="artifact_id"]\')?.remove()' in renderer
    assert "window.history.replaceState({}, '', url)" in renderer


def test_registry_minimap_matches_k8s_graph_overview_and_redraw_contract() -> None:
    template = (ROOT / 'app/templates/artifact_registry/partials/_topology_inspector_templates.html').read_text(
        encoding='utf-8'
    )
    renderer = RUNTIME_JS.read_text(encoding='utf-8')
    k8s = (ROOT / 'app/static/js/kubernetes/inventory/topology.js').read_text(encoding='utf-8')
    assert 'data-minimap' in template
    for feature in (
        'window.devicePixelRatio',
        'ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)',
        "token('--kaori-surface-card'",
        "token('--kaori-outline-strong'",
        "token('--kaori-status-info'",
        'ctx.setLineDash([4, 3])',
        "node.union(node.successors('node')).filter(':visible')",
        'nodeIds.has(edge.source().id()) && nodeIds.has(edge.target().id())',
        'const scheduleDrawerMiniMapUpdate = () =>',
        "cy.on('pan zoom resize position layoutstop', scheduleDrawerMiniMapUpdate)",
        "window.addEventListener('resize', scheduleDrawerMiniMapUpdate)",
        "drawing.dataset.kaoriBound = 'true'",
    ):
        assert feature in renderer
    assert 'window.devicePixelRatio' in k8s
    assert 'ctx.setLineDash([4, 3])' in k8s
    assert 'const drawMiniMap = (pane, node)' not in renderer


def test_resource_list_scrolls_without_pagination_and_matches_k8s() -> None:
    template = REGISTRY.read_text(encoding='utf-8')
    renderer = RUNTIME_JS.read_text(encoding='utf-8')
    k8s = K8S.read_text(encoding='utf-8')
    assert 'id="registry-topology-view-panel-list"' in template
    assert 'kaori-visualization-canvas h-[38rem] min-w-0 overflow-auto overscroll-contain bg-surface-card' in template
    assert 'topology-view-panel-list' in k8s
    assert 'overflow-auto bg-surface-card' in k8s
    assert 'registry-topology-resource-rows' in template
    assert 'registry-topology-prev' not in template
    assert 'registry-topology-next' not in template
    assert 'registry-topology-list-count' not in template
    assert 'registry-topology-prev' not in renderer
    assert 'registry-topology-next' not in renderer
    assert 'listPage' not in renderer
    assert 'pageSize' not in renderer
    assert 'const nodes = sortedVisibleResources()' in renderer
    assert 'for (const item of nodes)' in renderer
    assert 'const summary = payload.summary' in renderer
    assert 'summary.omitted_bindings' in renderer
    assert 'Dashed: scope · Solid: runtime/ownership.' in template
    assert 'Tag/mixed matches: see Details for confidence.' in template
    assert template.count('whitespace-nowrap text-xs text-') >= 2


def test_runtime_inspector_evidence_cards_preserve_committed_match_and_security() -> None:
    inspector = (ROOT / 'app/templates/artifact_registry/partials/_topology_inspector_templates.html').read_text(
        encoding='utf-8'
    )
    renderer = RUNTIME_JS.read_text(encoding='utf-8')
    Environment().parse(inspector)
    for marker in (
        'registry-topology-runtime-evidence-row-template',
        'data-node-runtime-bindings',
        'data-runtime-evidence-count',
        'data-runtime-evidence-rows',
        'data-runtime-workload',
        'data-runtime-pod',
        'data-runtime-cluster',
        'data-runtime-namespace',
        'data-runtime-match-text',
        'data-runtime-security-text',
        'data-runtime-match-dot',
        'data-runtime-security-dot',
    ):
        assert marker in inspector
    assert 'const rows = associatedBindings(node.id())' in renderer
    assert 'rows.slice(0, 10)' in renderer
    assert "String(item.match_type || item.match || '').toLowerCase()" in renderer
    assert 'item.confidence' in renderer
    assert "Number(item.critical) > 0 ? 'critical'" in renderer
    assert "Number(item.high) > 0 ? 'warning'" in renderer
    assert re.search(
        r"applyStatusSurface\(\s*"
        r"card\.querySelector\('\[data-runtime-match\]'\),\s*"
        r"card\.querySelector\('\[data-runtime-match-dot\]'\),\s*matchTone",
        renderer,
    )
    assert re.search(
        r"applyStatusSurface\(\s*"
        r"card\.querySelector\('\[data-runtime-security\]'\),\s*"
        r"card\.querySelector\('\[data-runtime-security-dot\]'\),\s*securityTone",
        renderer,
    )
    assert "'registry-topology-runtime-evidence-row-template'" in renderer
    assert 'rows.length - 10' in renderer
