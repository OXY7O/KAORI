from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROUTE_FILES = (
    ROOT / 'app/kubernetes_operations/configmaps/routes.py',
    ROOT / 'app/kubernetes_operations/secrets/crud_routes.py',
    ROOT / 'app/kubernetes_operations/secrets/reveal_routes.py',
    ROOT / 'app/kubernetes_operations/secrets/tls_routes.py',
)


def _decorator_name(node: ast.expr) -> str:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return ''


def test_cluster_readiness_is_never_a_blueprint_before_request_shortcut() -> None:
    root_routes = (ROOT / 'app/kubernetes_operations/routes.py').read_text(encoding='utf-8')

    assert '.before_request' not in root_routes
    assert 'has_registered_clusters' not in root_routes


def test_protected_operations_authorize_before_cluster_prerequisite() -> None:
    protected_functions = 0
    for path in ROUTE_FILES:
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            names = [_decorator_name(decorator) for decorator in node.decorator_list]
            if 'cluster_required' not in names:
                continue
            protected_functions += 1
            permission_indexes = [
                index for index, name in enumerate(names) if name in {'permission_required', 'any_permission_required'}
            ]
            assert permission_indexes, f'{path.name}:{node.name} has cluster_required without RBAC'
            assert min(permission_indexes) < names.index('cluster_required'), (
                f'{path.name}:{node.name} must authorize before checking cluster readiness'
            )

    assert protected_functions >= 30


def test_secret_security_boundaries_keep_sensitive_values_out_of_persistence_and_reveal() -> None:
    create_service = (ROOT / 'app/kubernetes_operations/secrets/create_service.py').read_text(encoding='utf-8')
    replace_service = (ROOT / 'app/kubernetes_operations/secrets/replace_service.py').read_text(encoding='utf-8')
    reveal_service = (ROOT / 'app/kubernetes_operations/secrets/reveal_service.py').read_text(encoding='utf-8')

    assert 'scrub_secret_payload(created)' in create_service
    assert 'scrub_mapping_values(encoded_data)' in replace_service
    assert "BLOCKED_KEY_NAMES = {'tls.key', 'ssh-privatekey'}" in reveal_service
    assert 'scrub_mapping_values(secret_data)' in reveal_service
    assert 'scrub_secret_payload(secret_object)' in reveal_service
    assert 'query.enable_eagerloads(False).with_for_update(of=SecretRevealRequest)' in reveal_service
    assert 'query = query.with_for_update()' not in reveal_service
