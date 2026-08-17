from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROUTE_FILES = tuple(sorted((ROOT / 'app/analytics').glob('*/routes.py'))) + (ROOT / 'app/analytics/routes.py',)


def _decorator_name(node: ast.expr) -> str:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return ''


def test_user_facing_analytics_routes_are_permission_guarded() -> None:
    protected = 0
    for path in ROUTE_FILES:
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decorators = [_decorator_name(item) for item in node.decorator_list]
            if any(name in {'route', 'get', 'post'} for name in decorators):
                assert 'permission_required' in decorators, f'{path.name}:{node.name} missing analytics RBAC'
                protected += 1
    assert protected >= 3


def test_analytics_route_layer_does_not_execute_provider_queries_directly() -> None:
    forbidden = (
        'MetricsConsumer(',
        'MetricsService(',
        '.query_range(',
        '.custom_query(',
        'get_alertmanager_alerts(',
        'load_alerts_by_source(',
    )
    for path in ROUTE_FILES:
        source = path.read_text(encoding='utf-8')
        for token in forbidden:
            assert token not in source, f'{path} executes provider work through {token}'


def test_analytics_partial_routes_keep_direct_navigation_on_full_page_boundaries() -> None:
    sources = '\n'.join(path.read_text(encoding='utf-8') for path in ROUTE_FILES)
    assert 'HX-Request' in sources
    assert 'request.headers.get' in sources
    assert 'redirect(' in sources
    assert "'Cache-Control'" in sources
