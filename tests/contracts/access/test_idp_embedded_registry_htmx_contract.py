"""Provider Registry HTMX responses must preserve workspace-owned framing."""

import ast
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = ROOT / 'app/templates/access/identity_providers/partials/_registry.html'
ROUTES_PATH = ROOT / 'app/access/identity_providers/routes.py'


def test_htmx_registry_target_is_rendered_embedded() -> None:
    source = ROUTES_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    view = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == 'index'
    )
    code = ast.get_source_segment(source, view)
    assert code is not None
    assert "request.headers.get('HX-Target') == 'identity-provider-workspace'" in code
    assert "render_template('access/identity_providers/partials/_workspace.html', **payload)" in code
    assert (
        "render_template('access/identity_providers/partials/_registry.html', "
        'embedded=True, **payload)'
    ) in code
    assert "request.headers.get('HX-History-Restore-Request') != 'true'" in code
    assert "render_template('access/identity_providers/index.html', **payload)" in code


def test_registry_root_is_frameless_when_embedded_but_standalone_is_framed() -> None:
    registry = REGISTRY_PATH.read_text(encoding='utf-8')
    Environment().parse(registry)

    root_start = registry.index('<section id="identity-provider-registry"')
    root_end = registry.index('>', root_start) + 1
    root = Environment().from_string(registry[root_start:root_end])
    table = SimpleNamespace(block_classes=lambda: 'rounded-xl border shadow-sm')

    embedded = root.render(table_ui=table, embedded=True)
    standalone = root.render(table_ui=table, embedded=False)
    assert 'rounded-xl' not in embedded
    assert 'border shadow-sm' not in embedded
    assert 'rounded-xl border shadow-sm' in standalone


def test_workspace_owns_frame_without_disturbing_registry_interactions() -> None:
    workspace = (
        ROOT / 'app/templates/access/identity_providers/partials/_workspace.html'
    ).read_text(encoding='utf-8')
    registry = REGISTRY_PATH.read_text(encoding='utf-8')

    assert 'class="{{ table_ui.block_classes() }}"' in workspace
    assert '{% set embedded = true %}' in workspace
    assert "partials/_tabs.html" in workspace
    assert "partials/_registry.html" in workspace
    for interaction in (
        'registry_ui.filter_form(',
        'registry_ui.clear_filters_link(',
        'registry_ui.footer(',
        'expandable.static_detail_row(',
        'name="tab" value="providers"',
    ):
        assert interaction in registry
