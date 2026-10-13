"""Kubernetes Topology is the presentation authority for every KAORI topology.

The Registry renderer keeps provider-specific evidence, while toolbar and
list/inspector row markup stay shared and must render identical DOM geometry.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates'


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_shared_topology_primitives_render_both_domain_template_ids() -> None:
    environment = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    primitives = environment.get_template('components/topology_primitives.html').module

    for template_id in ('topology-resource-list-row-template', 'registry-topology-resource-list-row-template'):
        rendered = str(primitives.resource_row_template(template_id))
        assert f'id="{template_id}"' in rendered
        for item in (
            'data-list-icon-shell',
            'data-list-icon',
            'data-list-name',
            'data-list-kind',
            'data-list-type',
            'data-list-cluster',
            'data-list-namespace',
            'data-list-status',
            'data-list-status-dot',
            'data-list-status-text',
            'data-list-relationships',
            'data-list-details',
        ):
            assert item in rendered
        assert 'View Details' in rendered

    for template_id in ('topology-field-row-template', 'registry-topology-field-row-template'):
        rendered = str(primitives.field_row_template(template_id))
        assert f'id="{template_id}"' in rendered
        assert 'data-field-label' in rendered
        assert 'data-field-value' in rendered

    for template_id in ('topology-relationship-row-template', 'registry-topology-inspector-relationship-row-template'):
        rendered = str(primitives.relationship_row_template(template_id))
        assert f'id="{template_id}"' in rendered
        assert 'data-topology-related-node' in rendered
        assert 'data-relationship-direction' in rendered
        assert 'data-relationship-label' in rendered
        assert 'data-relationship-peer' in rendered

    for macro in ('relationship_summary_item_template', 'relationship_empty_template'):
        assert str(getattr(primitives, macro)('test-topology-template'))


def test_both_topologies_consume_the_same_presentation_primitives() -> None:
    k8s = _read('app/templates/kubernetes/inventory/topology/partials/_workspace.html')
    registry = _read('app/templates/artifact_registry/topology.html')
    k8s_rows = _read('app/templates/kubernetes/inventory/topology/partials/_inspector_templates.html')
    registry_rows = _read('app/templates/artifact_registry/partials/_topology_inspector_templates.html')

    assert 'components/topology_primitives.html' in k8s
    assert 'components/topology_primitives.html' in registry
    assert 'topology_parts.toolbar_button_classes()' in k8s
    assert 'topology_parts.toolbar_button_classes()' in registry
    assert 'topology_parts.toolbar_export_classes()' in k8s
    assert 'topology_parts.toolbar_export_classes()' in registry

    for macro in (
        'resource_row_template',
        'field_row_template',
        'relationship_row_template',
        'relationship_summary_item_template',
        'relationship_empty_template',
    ):
        assert f'topology_parts.{macro}(' in k8s_rows
        assert f'topology_parts.{macro}(' in registry_rows


def test_registry_typography_and_semantics_match_k8s_not_provider_health() -> None:
    registry = _read('app/static/js/artifact_registry/topology.js')
    k8s = _read('app/static/js/kubernetes/inventory/topology.js')
    for style in (
        "'font-weight': 400",
        "'text-max-width': 220",
        "'text-overflow-wrap': 'normal'",
        "'line-height': 1.2",
        "'min-zoomed-font-size': 8",
        "'text-valign': 'bottom'",
    ):
        assert style in registry
        assert style in k8s
    assert "const displayLabel = (value) => String(value || 'Not Reported')" in registry
    assert 'const evidenceStatus = (data) =>' in registry
    assert "data.type === 'artifact'" in registry
    assert 'critical > 0' in registry
    assert 'high > 0' in registry
    assert "readiness.status === 'ready' ? 'info'" in registry
    assert 'payload.summary.omitted_bindings' in registry
    assert 'max-w-[18rem]' in _read('app/templates/components/topology_primitives.html')
