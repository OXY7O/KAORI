from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TOPOLOGY_JS = ROOT / 'app/static/js/kubernetes/inventory/topology.js'
TOPOLOGY_TEMPLATE = (
    ROOT / 'app/templates/kubernetes/inventory/topology/partials/_workspace.html'
)
TOPOLOGY_PATTERN = ROOT / 'docs/design/patterns/KUBERNETES_TOPOLOGY.md'


def test_dense_topology_has_compact_hierarchy_without_layout_level_autofit() -> None:
    source = TOPOLOGY_JS.read_text(encoding='utf-8')

    # Both layouts leave viewport ownership to the shared post-layout fit function.
    hierarchy = source.split("name: 'breadthfirst',", maxsplit=1)[1]
    hierarchy = hierarchy.split('}', maxsplit=1)[0]
    dependency = source.split("name: 'cose',", maxsplit=1)[1].split('}', maxsplit=1)[0]
    assert 'fit: false' in hierarchy
    assert 'fit: false' in dependency
    assert 'nodeDimensionsIncludeLabels: true' in hierarchy
    assert 'nodeDimensionsIncludeLabels: true' in dependency
    assert 'visibleCount <= 8 ? 1.18 : visibleCount <= 35 ? 1.13 : 1.24' in hierarchy
    assert 'idealEdgeLength: 210' in dependency  # Retain approved COSE geometry.


def test_dense_graph_focus_and_explicit_fit_keep_distinct_meaning() -> None:
    source = TOPOLOGY_JS.read_text(encoding='utf-8')
    assert 'const DENSE_NODE_THRESHOLD = 12' in source
    assert 'const DENSE_ZOOM_THRESHOLD = 0.72' in source
    assert 'const READABLE_ZOOM = 0.82' in source
    bbox_token = 'visible.boundingBox({ includeLabels: true, includeOverlays: false })'
    assert bbox_token in source
    assert 'cy.fit(bounds, padding)' in source
    assert 'preferReadable &&' in source
    assert 'cy.center(readableFocusNode(visible.nodes()))' in source
    assert "node.data('type') === 'namespace'" in source
    assert "node.data('type') === 'cluster'" in source
    fit_button = "'topology-fit-button')?.addEventListener('click', fitGraphToCanvas)"
    assert fit_button in source
    assert 'fitGraphToCanvas({ preferReadable: true })' in source


def test_dense_topology_viewport_hint_is_accessible_and_nonblocking() -> None:
    source = TOPOLOGY_JS.read_text(encoding='utf-8')
    template = TOPOLOGY_TEMPLATE.read_text(encoding='utf-8')
    pattern = TOPOLOGY_PATTERN.read_text(encoding='utf-8')
    for element_id in (
        'topology-viewport-hint',
        'topology-viewport-hint-title',
        'topology-viewport-hint-count',
        'topology-viewport-hint-description',
    ):
        assert f'id="{element_id}"' in template
    assert 'role="status"' in template
    assert 'aria-live="polite"' in template
    assert 'pointer-events-none absolute' in template
    assert 'border-outline-subtle bg-surface-card' in template
    assert 'sm:w-80' in template
    assert 'truncate whitespace-nowrap text-xs' in template
    assert 'bg-kaori-soft text-kaori-primary' in template
    assert 'Pan to explore · Fit for overview.' in source
    assert 'Zoom for labels · Use Resource List.' in source
    assert 'viewportHintTitle.textContent = readableFocusActive' in source
    assert "'Focused view' : 'Full graph overview'" in source
    assert 'viewportHintCount.textContent = `${nodeCount} resources`' in source
    assert 'const updateViewportHint = (nodeCount) =>' in source
    assert 'viewportHint.textContent' not in source
    assert 'focused viewport' in pattern.lower() or 'focal viewport' in pattern.lower()


def test_dense_topology_retains_operator_pan_zoom_and_export_scope() -> None:
    source = TOPOLOGY_JS.read_text(encoding='utf-8')
    assert 'if (!graphViewportInitialized)' in source
    assert 'fitGraphToCanvas({ preferReadable: true })' in source
    assert '!readableFocusActive &&' in source
    assert 'visible.layout(layoutOptions()).run()' in source
    assert 'exportJson = () =>' in source
    assert 'exportPng = () =>' in source
    assert 'visibleNodeRecords().map((node) => node.data())' in source
    assert "const visibleEdges = cy" in source
    assert "updateViewportHint(visible.nodes().length)" in source
