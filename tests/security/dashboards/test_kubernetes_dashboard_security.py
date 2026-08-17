from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROUTES = ROOT / 'app/kubernetes/dashboard/routes.py'
DASHBOARD_PACKAGE = ROOT / 'app/kubernetes/dashboard'


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)


def _permission(function: ast.FunctionDef) -> str | None:
    for decorator in function.decorator_list:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Name):
            continue
        if decorator.func.id != 'permission_required' or not decorator.args:
            continue
        value = decorator.args[0]
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
    return None


def test_dashboard_routes_keep_dashboard_view_as_the_explicit_authorization_boundary() -> None:
    tree = ast.parse(ROUTES.read_text(encoding='utf-8'))

    assert _permission(_function(tree, 'index')) == 'dashboard.view'
    assert _permission(_function(tree, 'section')) == 'dashboard.view'


def test_dashboard_web_package_has_no_direct_provider_client_or_network_boundary() -> None:
    source = '\n'.join(path.read_text(encoding='utf-8') for path in DASHBOARD_PACKAGE.rglob('*.py'))
    forbidden = (
        'kubernetes.client',
        'prometheus_api_client',
        'requests.get(',
        'requests.post(',
        'httpx.',
        'urllib.request',
        'boto3.client',
    )

    assert all(token not in source for token in forbidden)
    assert 'read_dashboard_snapshot(' in source


def test_dashboard_has_no_blueprint_before_request_authorization_shortcut() -> None:
    tree = ast.parse(ROUTES.read_text(encoding='utf-8'))

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            called = decorator.func if isinstance(decorator, ast.Call) else decorator
            assert not (isinstance(called, ast.Attribute) and called.attr == 'before_request')
