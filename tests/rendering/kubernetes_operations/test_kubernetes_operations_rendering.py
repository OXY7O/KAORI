from __future__ import annotations

from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates/kubernetes/operations'
FORM_CONTEXT_TEMPLATES = (
    TEMPLATES / 'configmaps/create.html',
    TEMPLATES / 'configmaps/update.html',
    TEMPLATES / 'configmaps/delete.html',
    TEMPLATES / 'secrets/create.html',
    TEMPLATES / 'secrets/replace.html',
    TEMPLATES / 'secrets/delete.html',
    TEMPLATES / 'secrets/reveal.html',
)


def test_kubernetes_operations_templates_parse_with_jinja() -> None:
    environment = Environment()
    templates = sorted(TEMPLATES.rglob('*.html'))

    assert len(templates) >= 40
    for template in templates:
        environment.parse(template.read_text(encoding='utf-8'))


def test_reviewed_form_context_workspaces_use_shared_geometry_without_page_local_ui_debt() -> None:
    for template in FORM_CONTEXT_TEMPLATES:
        source = template.read_text(encoding='utf-8')
        lowered = source.lower()

        assert 'data-kubernetes-operation-layout="form-context-v1"' in source
        assert 'components/form_with_context_rail.html' in source
        assert 'form_context.layout_classes()' in source
        assert 'form_context.main_classes()' in source
        assert 'form_context.rail_classes()' in source
        assert ' style=' not in lowered
        assert ' onclick=' not in lowered
        assert ' onchange=' not in lowered
