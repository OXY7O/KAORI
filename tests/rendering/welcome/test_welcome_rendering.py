from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_ROOT = ROOT / 'app/templates'


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_ROOT),
        autoescape=select_autoescape(('html', 'xml')),
        undefined=StrictUndefined,
    )


def test_welcome_template_and_shared_components_compile_together() -> None:
    environment = _environment()

    for template_name in (
        'welcome/index.html',
        'components/page_hero.html',
        'components/welcome_capability_group.html',
        'components/workspace_link_card.html',
        'components/states/_empty_state.html',
    ):
        environment.get_template(template_name)


def test_welcome_rendering_uses_canonical_hero_and_accessible_catalog_contract() -> None:
    template = (TEMPLATE_ROOT / 'welcome/index.html').read_text(encoding='utf-8')
    card = (TEMPLATE_ROOT / 'components/workspace_link_card.html').read_text(encoding='utf-8')

    assert "page_hero.context_header('Access Scope', 'Role-Aware Workspace', 'key-round')" in template
    assert '<span class="sr-only">Search Available Workspaces</span>' in template
    assert 'aria-live="polite"' in template
    assert 'components/states/_empty_state.html' in template
    assert 'aria-label="Open {{ workspace.title }} Workspace"' in card
    assert 'focus-visible:ring-2' in card
    assert ' style=' not in template.lower()
    assert ' onclick=' not in template.lower()
