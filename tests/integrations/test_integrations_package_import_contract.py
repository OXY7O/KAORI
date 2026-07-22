from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_INIT = ROOT / 'app' / 'integrations' / '__init__.py'


def test_integrations_package_has_no_route_import_or_lazy_export() -> None:
    source = PACKAGE_INIT.read_text(encoding='utf-8')
    tree = ast.parse(source)

    route_imports = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == 'app.integrations.routes'
    ]

    assert route_imports == []
    assert 'def __getattr__(' not in source
    assert '__all__' not in source
    assert 'integrations_bp' not in source


def test_application_registers_integrations_blueprint_explicitly() -> None:
    application = (ROOT / 'app' / '__init__.py').read_text(encoding='utf-8')

    assert 'from app.integrations.routes import integrations_bp' in application
    assert 'app.register_blueprint(integrations_bp)' in application
