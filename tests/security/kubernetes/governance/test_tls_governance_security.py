from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
GOVERNANCE_ROUTES = ROOT / 'app/kubernetes/governance/routes.py'
TLS_ROUTES = ROOT / 'app/kubernetes/governance/tls_certificates/routes.py'


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


def test_governance_blueprint_has_no_before_request_security_shortcut() -> None:
    tree = ast.parse(GOVERNANCE_ROUTES.read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            assert all(_called_name(decorator) != 'before_request' for decorator in node.decorator_list)


def test_tls_routes_keep_view_and_sync_permissions_as_explicit_boundaries() -> None:
    tree = ast.parse(TLS_ROUTES.read_text(encoding='utf-8'))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

    assert _permission(functions['tls_certificates_index']) == 'tls_certificates.view'
    assert _permission(functions['tls_certificates_detail']) == 'tls_certificates.view'
    assert _permission(functions['tls_certificates_sync']) == 'tls_certificates.sync'
    assert _permission(functions['tls_certificates_sync_status']) == 'tls_certificates.sync'


def test_tls_security_boundary_keeps_user_scoped_job_visibility_and_secret_data_minimization() -> None:
    routes = TLS_ROUTES.read_text(encoding='utf-8')
    collector = (ROOT / 'app/kubernetes/governance/tls_certificates/collector.py').read_text(encoding='utf-8')
    mutation = (ROOT / 'app/kubernetes/governance/tls_certificates/mutation.py').read_text(encoding='utf-8')

    assert 'get_visible_tls_sync_job(public_id=public_id, user_id=int(current_user.id))' in routes
    assert '(secret.data or {}).get(TLS_CRT_KEY)' in collector
    assert '(secret.data or {}).get(TLS_KEY_KEY)' not in collector
    assert 'scrub_secret_payload(live_secret)' in mutation
    assert 'scrub_mapping_values(encoded_data)' in mutation
