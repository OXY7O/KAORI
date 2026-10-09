import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment, FileSystemLoader

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
    assert "snapshot.status == 'missing'" in ui
    assert "can_bootstrap and can_manage" in ui
    assert "can_bootstrap and not can_manage" in ui
    assert 'disabled' not in ui
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


def _render_capsule_rbac_panel(snapshot: dict | None, *, can_manage: bool = True) -> str:
    templates = Environment(
        loader=FileSystemLoader(str(ROOT / 'app/templates')),
        autoescape=True,
    )
    template = templates.get_template(
        'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/'
        '_capsule_rbac_bootstrap.html'
    )
    permissions = (
        {'clusters.sync', 'clusters.manage', 'integrations.manage'}
        if can_manage else {'clusters.sync'}
    )
    return template.render(
        capsule_rbac_bootstrap=snapshot,
        cluster=SimpleNamespace(id='cluster-a', name='Kubernetes X300'),
        current_user=SimpleNamespace(has_permission=lambda permission: permission in permissions),
        url_for=lambda endpoint, **kwargs: f'/test/{endpoint}',
        csrf_token=lambda: 'test-csrf',
    )


def _role(status: str, *, name: str = 'kaori-tenant-viewer-v1', reason: str = '') -> dict:
    return {
        'name': name,
        'profile': 'Viewer',
        'version': 1,
        'status': status,
        'reason': reason,
        'uid': 'cluster-role-uid' if status != 'missing' else None,
        'resource_version': '17' if status != 'missing' else None,
        'permissions_sha256': 'abc0123456789',
    }


def _snapshot(status: str, roles: list[dict]) -> dict:
    return {
        'status': status,
        'operation': 'check',
        'checked_at': '2026-10-09T07:42:21+00:00',
        'roles': roles,
        'ready': sum(role['status'] == 'ready' for role in roles),
        'missing': sum(role['status'] == 'missing' for role in roles),
        'conflict': sum(role['status'] == 'conflict' for role in roles),
    }


def test_capsule_rbac_ready_state_uses_completion_action_not_mutation_approval() -> None:
    html = _render_capsule_rbac_panel(_snapshot('ready', [_role('ready')]))

    assert 'Cluster RBAC prerequisites ready' in html
    assert 'All canonical ClusterRoles match. No bootstrap is required.' in html
    assert 'Review Access Grants' in html
    assert 'Check RBAC' in html
    assert 'cluster-role-uid' in html
    assert 'abc0123456789' in html
    assert '2026-10-09 07:42:21 UTC' in html
    assert 'Bootstrap Missing Roles' not in html
    assert 'name="confirm_cluster_rbac"' not in html
    assert 'capsule-rbac/bootstrap' not in html


def test_capsule_rbac_missing_state_shows_approved_mutation_only_to_operator() -> None:
    snapshot = _snapshot('missing', [_role('missing')])
    html = _render_capsule_rbac_panel(snapshot)

    assert 'Missing ClusterRoles can be prepared' in html
    assert 'Bootstrap Missing Roles' in html
    assert 'name="confirm_cluster_rbac"' in html
    assert 'value="approved"' in html
    assert 'required' in html
    assert 'capsule-rbac/bootstrap' in html
    assert 'Bootstrap blocked by a role conflict' not in html

    readonly_html = _render_capsule_rbac_panel(snapshot, can_manage=False)
    assert 'An authorized cluster operator' in readonly_html
    assert 'name="confirm_cluster_rbac"' not in readonly_html
    assert 'Bootstrap Missing Roles' not in readonly_html


@pytest.mark.parametrize(
    ('status', 'roles', 'expected'),
    [
        ('conflict', [_role('conflict', reason='Broader verbs detected')], 'Bootstrap blocked by a role conflict'),
        ('failed', [_role('missing')], 'RBAC operation needs attention'),
        ('started', [_role('missing')], 'Check RBAC to refresh committed prerequisite evidence'),
    ],
)
def test_capsule_rbac_blocked_states_never_offer_bootstrap(
    status: str, roles: list[dict], expected: str
) -> None:
    snapshot = _snapshot(status, roles)
    snapshot['reason'] = 'Incomplete verification'
    html = _render_capsule_rbac_panel(snapshot)

    assert expected in html
    assert 'Bootstrap Missing Roles' not in html
    assert 'name="confirm_cluster_rbac"' not in html
    assert 'capsule-rbac/bootstrap' not in html


def test_capsule_rbac_empty_and_untrusted_evidence_are_safe() -> None:
    html = _render_capsule_rbac_panel(None)
    assert 'Not Checked' in html
    assert 'Run Check RBAC' in html
    assert 'Bootstrap Missing Roles' not in html

    snapshot = _snapshot('conflict', [_role('conflict', reason='<script>alert(1)</script>')])
    html = _render_capsule_rbac_panel(snapshot)
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html
