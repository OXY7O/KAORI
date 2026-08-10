from __future__ import annotations

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates/kubernetes_operations'
MUTATION_TEMPLATES = (
    TEMPLATES / 'configmaps/create.html',
    TEMPLATES / 'configmaps/update.html',
    TEMPLATES / 'configmaps/delete.html',
    TEMPLATES / 'secrets/create.html',
    TEMPLATES / 'secrets/replace.html',
    TEMPLATES / 'secrets/delete.html',
    TEMPLATES / 'secrets/reveal.html',
    TEMPLATES / 'secrets/tls_rotation.html',
)


def test_kubernetes_operations_templates_parse_with_jinja() -> None:
    environment = Environment()
    templates = sorted(TEMPLATES.rglob('*.html'))

    assert len(templates) >= 40
    for template in templates:
        environment.parse(template.read_text(encoding='utf-8'))


def test_mutation_workspaces_use_full_width_shared_components_without_page_local_ui_debt() -> None:
    for template in MUTATION_TEMPLATES:
        source = template.read_text(encoding='utf-8')
        lowered = source.lower()

        assert 'data-kubernetes-operation-layout="full-width-v2"' in source
        assert 'context_rail.html' not in source
        assert 'context_rail.layout_classes' not in source
        assert 'context_rail.rail_classes' not in source
        assert ' style=' not in lowered
        assert ' onclick=' not in lowered
        assert ' onchange=' not in lowered
