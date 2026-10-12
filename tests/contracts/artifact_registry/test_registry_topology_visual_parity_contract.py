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
    assert "components/states/_empty_state.html" in registry


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
        "nodeDimensionsIncludeLabels: true",
        "includeLabels: true",
        "name: 'breadthfirst'",
        "name: 'cose'",
    ):
        assert phrase in renderer
        assert phrase in canonical

    assert "width: 76" in renderer
    assert "height: 44" in renderer
    assert "badgeImage(node.data())" in renderer
    assert "transform: (_node, position) => ({ x: position.y, y: position.x })" in renderer
    assert "'line-style': (edge) => edge.data('relationship') === 'contains'" in renderer
    assert "selector: 'edge[relationship = \"contains\"]'" in renderer
    assert "'curve-style': 'taxi'" in renderer
    assert "'taxi-direction': 'horizontal'" in renderer
    assert "selector: 'edge.edge-label-visible'" in renderer
    assert "selector: 'edge.edge-hovered'" in renderer
    assert "cy.on('mouseover', 'edge'" in renderer
    assert "cy.on('mouseout', 'edge'" in renderer
    assert "updateEdgeLabelClasses()" in renderer
    assert "'kaori-topology-muted'" in renderer
    assert "graphHasLayout" in renderer
    assert "aria-selected" in renderer
    assert "closePane()" in renderer
    assert "scopeSummary.textContent" in renderer
    assert "summary.omitted_bindings" in renderer
    assert "evidence.status !== 'ready'" in renderer
    assert "URL.createObjectURL(new Blob(" in renderer
    assert "canvas.dataset.rendererUrl" in renderer
    assert not re.search(r'#[0-9A-Fa-f]{3,8}\b', renderer)

    palette = PALETTE.read_text(encoding='utf-8')
    assert 'External Label Node' in palette
    assert 'raw hex' in palette.lower()
    assert "kaori-topology-domain-configuration" in REGISTRY.read_text(encoding='utf-8')


def test_visual_refactor_does_not_move_registry_evidence_authority() -> None:
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text(encoding='utf-8')
    projection = (ROOT / 'app/artifact_registry/presentation_topology.py').read_text(encoding='utf-8')
    assert 'build_dependency_topology(**_runtime_topology_filters())' in routes
    assert "@permission_required('artifact_registry.view')" in routes
    assert 'RegistryWorkloadBinding' in projection
    assert '.limit(_MAX_VISIBLE_BINDINGS)' in projection
    assert 'runtime_correlation_evidence_readiness' in projection
