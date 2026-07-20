from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_INIT = ROOT / 'app' / 'integrations' / '__init__.py'


def test_integrations_package_does_not_eagerly_import_routes() -> None:
    tree = ast.parse(PACKAGE_INIT.read_text(encoding='utf-8'))

    eager_route_imports = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == 'app.integrations.routes'
    ]

    assert eager_route_imports == []


def test_integrations_blueprint_remains_available_through_lazy_export() -> None:
    source = PACKAGE_INIT.read_text(encoding='utf-8')

    assert "__all__ = ['integrations_bp']" in source
    assert "def __getattr__(name: str)" in source
    assert "if name == 'integrations_bp':" in source
    assert 'from app.integrations.routes import integrations_bp' in source
