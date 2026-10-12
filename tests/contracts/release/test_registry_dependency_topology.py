"""Contract guards for committed Registry runtime dependency topology (#1692).

These tests protect the source/evidence boundary; database-backed correctness
and visual UAT remain separate admission requirements.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECTION = ROOT / 'app/artifact_registry/presentation_topology.py'
ROUTES = ROOT / 'app/artifact_registry/routes.py'
RUNTIME = ROOT / 'app/templates/artifact_registry/partials/_runtime_workspace.html'
TEMPLATE = ROOT / 'app/templates/artifact_registry/topology.html'
RENDERER = ROOT / 'app/static/js/artifact_registry/topology.js'
STANDARD = ROOT / 'app/templates/components/visualization_workspace.html'


def test_topology_is_a_bounded_committed_binding_projection() -> None:
    source = PROJECTION.read_text(encoding='utf-8')
    ast.parse(source, filename=str(PROJECTION))
    assert 'RegistryWorkloadBinding' in source
    assert '_runtime_filtered_query' in source
    assert '_providers()' in source
    assert 'query.order_by(None).count()' in source
    assert '.limit(_MAX_VISIBLE_BINDINGS)' in source
    assert '_MAX_VISIBLE_BINDINGS = 45' in source
    assert 'omitted_bindings' in source
    assert 'runtime_correlation_evidence_readiness' in source
    assert "confidence_by_edge" in source
    assert 'mixed' in source
    assert 'HarborProvider(' not in source
    assert 'requests.get(' not in source
    assert 'subprocess.' not in source


def test_topology_routes_are_permission_scoped_and_linked_to_runtime() -> None:
    source = ROUTES.read_text(encoding='utf-8')
    assert "@artifact_registry_bp.get('/runtime/topology')" in source
    assert "@artifact_registry_bp.get('/runtime/topology/data')" in source
    for name in ('runtime_topology', 'runtime_topology_data'):
        signature = f'@permission_required(\'artifact_registry.view\')\ndef {name}('
        assert signature in source
    assert '_runtime_scope_id(\'source_id\')' in source
    assert '_runtime_scope_id(\'artifact_id\')' in source

    runtime = RUNTIME.read_text(encoding='utf-8')
    # Level-three integrated tabs own navigation; the legacy duplicate CTA
    # must not compete with the canonical workspace navigation above the Hero.
    assert 'Open Dependency Topology' not in runtime
    assert 'Runtime Bindings' in runtime


def test_topology_reuses_shared_workspace_with_accessible_list_fallback() -> None:
    template = TEMPLATE.read_text(encoding='utf-8')
    renderer = RENDERER.read_text(encoding='utf-8')
    assert STANDARD.exists()
    assert 'visualization.render(' in template
    assert "snapshot_context_bar.render(" in template
    assert 'role="img"' in template
    assert 'Resource List' in template
    assert 'registry-topology-resource-rows' in template
    assert 'aria-modal="true"' in template
    assert "filename='vendor/cytoscape/cytoscape.esm.min.js'" in template
    assert "filename='js/artifact_registry/topology.js'" in template
    assert 'window.KAORI_TOPOLOGY =' not in renderer
    assert "setView('list')" in renderer
    assert 'summary.omitted_bindings' in renderer
    assert 'evidence.status' in renderer
    assert 'textContent' in renderer
