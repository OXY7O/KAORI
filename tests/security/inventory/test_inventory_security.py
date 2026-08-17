from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROUTES = ROOT / 'app/inventory/kubernetes/routes.py'
READ_SIDE = (
    ROOT / 'app/inventory/kubernetes/overview.py',
    ROOT / 'app/inventory/kubernetes/resources',
    ROOT / 'app/inventory/kubernetes/topology',
)

READ_VIEWS = {
    'overview',
    'topology',
    'topology_data',
    'nodes',
    'node_details',
    'namespaces',
    'namespace_details',
    'configuration',
    'configuration_details',
    'workloads',
    'workload_details',
    'pods',
    'pod_details',
    'services',
    'service_details',
    'ingresses',
    'ingress_details',
    'storage',
    'storage_details',
}


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    return next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)


def _called_name(decorator: ast.expr) -> str | None:
    called = decorator.func if isinstance(decorator, ast.Call) else decorator
    if isinstance(called, ast.Name):
        return called.id
    if isinstance(called, ast.Attribute):
        return called.attr
    return None


def _permission(function: ast.FunctionDef) -> str | None:
    for decorator in function.decorator_list:
        if not isinstance(decorator, ast.Call) or _called_name(decorator) != 'permission_required':
            continue
        if decorator.args and isinstance(decorator.args[0], ast.Constant):
            return str(decorator.args[0].value)
    return None


def test_inventory_read_routes_authorize_before_clusterless_htmx_guard() -> None:
    tree = ast.parse(ROUTES.read_text(encoding='utf-8'))

    for name in READ_VIEWS:
        function = _function(tree, name)
        decorators = [_called_name(decorator) for decorator in function.decorator_list]
        assert _permission(function) == 'inventory.view', name
        assert '_clusterless_inventory_htmx_guard' in decorators, name
        assert decorators.index('permission_required') < decorators.index('_clusterless_inventory_htmx_guard'), name


def test_inventory_blueprint_has_no_before_request_response_shortcut() -> None:
    tree = ast.parse(ROUTES.read_text(encoding='utf-8'))

    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        assert all(_called_name(decorator) != 'before_request' for decorator in node.decorator_list)


def test_inventory_read_side_has_no_live_provider_or_network_client_boundary() -> None:
    chunks: list[str] = []
    for path in READ_SIDE:
        if path.is_dir():
            chunks.extend(item.read_text(encoding='utf-8') for item in path.rglob('*.py'))
        else:
            chunks.append(path.read_text(encoding='utf-8'))
    source = '\n'.join(chunks)
    forbidden = (
        'kubernetes.client',
        'get_integration(',
        'client.build',
        'requests.get(',
        'requests.post(',
        'httpx.',
        'urllib.request',
        'boto3.client',
        'app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.resolver',
    )

    assert all(token not in source for token in forbidden)
