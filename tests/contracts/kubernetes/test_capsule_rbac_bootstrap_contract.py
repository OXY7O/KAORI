import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_cluster_rbac_bootstrap_is_governed_separately_from_tenant_adoption():
    bootstrap = read('app/kubernetes/cluster/capsule_rbac_bootstrap.py')
    integrations = read('app/integrations/routes.py')
    detail = read('app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/detail.html')
    ui = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/'
        '_capsule_rbac_bootstrap.html'
    )
    access = read('app/kubernetes/tenant/access.py')
    adoption = read('app/kubernetes/tenant/discovery_adoption.py')

    assert "target_type=_TARGET" in bootstrap
    assert "latest_capsule_role_bootstrap_evidence" in bootstrap
    assert "capsule_cluster_role_manifest(profile)" in bootstrap
    assert "get_access_profile(key, LATEST_ACCESS_PROFILE_VERSION[key])" in bootstrap
    assert "api.create_cluster_role(body=_body(profile), dry_run='All'" in bootstrap
    assert "api.create_cluster_role(body=_body(profile), _request_timeout=5)" in bootstrap
    assert "a prior Check RBAC with missing roles" in bootstrap or "A prior Check RBAC with missing roles" in bootstrap
    assert "row['status'] == 'conflict'" in bootstrap
    assert "ClusterRole conflict detected" in bootstrap
    assert "'created': created" in bootstrap
    assert 'def capsule_cluster_role_manifest(' in access
    assert 'capsule_rbac_bootstrap' not in adoption
    assert "@integrations_bp.post('/kubernetes/<string:cluster_id>/capsule-rbac/check')" in integrations
    assert "@integrations_bp.post('/kubernetes/<string:cluster_id>/capsule-rbac/bootstrap')" in integrations
    assert "@permission_required('clusters.manage')" in integrations
    assert "@permission_required('integrations.manage')" in integrations
    assert 'validate_csrf(' in integrations
    assert "request.form.get('confirm_cluster_rbac') != 'approved'" in integrations
    assert '_capsule_rbac_bootstrap.html' in detail
    assert 'data-capsule-rbac-bootstrap' in ui
    assert 'Bootstrap Missing Roles' in ui
    assert 'Check RBAC' in ui
    assert 'name="confirm_cluster_rbac"' in ui
    assert "snapshot.status != 'missing'" in ui
    assert 'create_cluster_role(' not in ui
    assert 'ClusterRoleBinding' not in bootstrap
    assert "runtime_adapter.build_client(connection)" in bootstrap


def test_capsule_rbac_check_and_bootstrap_flash_feedback_has_flask_import() -> None:
    """Both POST handlers must resolve Flask flash; missing import produced HTTP 500."""
    tree = ast.parse(read('app/integrations/routes.py'))
    flask_imports = [
        item
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == 'flask'
        for item in node.names
    ]
    assert any(item.name == 'flash' and item.asname is None for item in flask_imports)

    for handler_name in ('kubernetes_capsule_rbac_check', 'kubernetes_capsule_rbac_bootstrap'):
        handlers = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == handler_name
        ]
        assert len(handlers) == 1
        assert any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == 'flash'
            for node in ast.walk(handlers[0])
        ), f'{handler_name} must notify the operator after its action'
