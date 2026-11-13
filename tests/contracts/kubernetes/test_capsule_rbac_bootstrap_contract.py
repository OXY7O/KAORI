import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_cluster_rbac_bootstrap_is_governed_separately_from_tenant_adoption():
    bootstrap = read('app/kubernetes/tenant/capsule_rbac_bootstrap.py')
    assert not (ROOT / 'app/kubernetes/cluster/capsule_rbac_bootstrap.py').exists()
    integrations = read('app/integrations/routes.py')
    tenant_web = read('app/integrations/orchestration/container_orchestrator/tenant_capsule_web.py')
    composition = read('app/bootstrap/blueprints.py')
    detail = read('app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/detail.html')
    ui = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/'
        '_capsule_rbac_bootstrap.html'
    )
    access = read('app/kubernetes/tenant/access.py')
    adoption = read('app/kubernetes/tenant/discovery_adoption.py')

    assert 'from app.kubernetes.tenant.capsule_rbac_bootstrap import (' not in integrations
    assert 'from app.kubernetes.tenant.capsule_rbac_bootstrap import (' in composition
    assert "app.extensions['kaori_tenant_capsule_rbac_bootstrap'] = {" in composition
    for operation in (
        'bootstrap_missing_capsule_roles',
        'check_capsule_role_bootstrap',
        'latest_capsule_role_bootstrap_evidence',
    ):
        assert f"'{operation}': {operation}" in composition
        assert f"capsule_rbac_operation('{operation}')" in integrations
    assert 'tenant_capsule_web import capsule_rbac_operation' in integrations
    assert "current_app.extensions.get('kaori_tenant_capsule_rbac_bootstrap')" in tenant_web
    assert 'if not callable(operation):' in tenant_web
    assert 'target_type=_TARGET' in bootstrap
    assert 'latest_capsule_role_bootstrap_evidence' in bootstrap
    assert 'capsule_cluster_role_manifest(profile)' in bootstrap
    assert 'get_access_profile(key, LATEST_ACCESS_PROFILE_VERSION[key])' in bootstrap
    assert "api.create_cluster_role(body=_body(profile), dry_run='All'" in bootstrap
    assert 'api.create_cluster_role(body=_body(profile), _request_timeout=5)' in bootstrap
    assert 'a prior Check RBAC with missing roles' in bootstrap or 'A prior Check RBAC with missing roles' in bootstrap
    assert "row['status'] == 'conflict'" in bootstrap
    assert 'ClusterRole conflict detected' in bootstrap
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
    assert 'can_bootstrap and can_manage' in ui
    assert 'can_bootstrap and not can_manage' in ui
    assert 'hx-disabled-elt="button"' in ui
    assert '<button type="submit" disabled' not in ui
    assert 'create_cluster_role(' not in ui
    assert 'ClusterRoleBinding' not in bootstrap
    assert 'runtime_adapter.build_client(connection)' in bootstrap


def test_capsule_rbac_actions_emit_canonical_feedback_in_both_request_modes() -> None:
    """Check and approved bootstrap must present one audited toast, never layout-shifting flash."""
    source = read('app/integrations/routes.py')
    tree = ast.parse(source)
    panel = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/'
        '_capsule_rbac_bootstrap.html'
    )
    feedback_oob = read('app/templates/components/operation_feedback_oob.html')
    toast = read('app/templates/components/operational_toast.html')

    flask_imports = [
        item for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == 'flask' for item in node.names
    ]
    assert not any(item.name == 'flash' for item in flask_imports)
    assert 'flash(' not in source

    for handler_name, operation in (
        ('kubernetes_capsule_rbac_check', 'check'),
        ('kubernetes_capsule_rbac_bootstrap', 'bootstrap'),
    ):
        handlers = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == handler_name]
        assert len(handlers) == 1
        body = ast.get_source_segment(source, handlers[0])
        assert body is not None
        assert "_capsule_rbac_feedback_response(cluster_id, result, operation='" + operation + "')" in body
        assert 'validate_csrf(' in body
        assert 'abort(404)' in body
    assert "request.form.get('confirm_cluster_rbac') != 'approved'" in source
    assert "@permission_required('clusters.sync')" in source
    assert "@permission_required('clusters.manage')" in source
    assert "@permission_required('integrations.manage')" in source

    assert 'from app.platform_operations.notifications.feedback import OperationalDeliveryPolicy' in source
    assert 'record_operational_activity(' in source
    assert "event_type=f'kubernetes_capsule_rbac_{operation}'" in source
    assert 'delivery_policy=OperationalDeliveryPolicy.DECK_ON_FAILURE' in source
    assert 'queue_feedback=not is_htmx' in source
    assert "provider_status = str(result.get('status') or 'failed')" in source
    for state in ("'ready'", "'missing'", "'conflict'", "'failed'"):
        assert state in source
    assert "'success'" in source and "'warning'" in source and "'error'" in source
    assert 'return redirect(destination)' in source
    assert "url_for('integrations.kubernetes_detail', cluster_id=cluster_id) + '#validation'" in source
    assert "'operation_feedback': feedback" in source
    assert "'notification_context': get_navigation_notification_context" in source
    assert "partials/_capsule_rbac_bootstrap.html'," in source

    for action in ('kubernetes_capsule_rbac_check', 'kubernetes_capsule_rbac_bootstrap'):
        assert f'hx-post="{{{{ url_for(\'integrations.{action}\', cluster_id=cluster.id) }}}}"' in panel
    assert panel.count('hx-target="closest [data-capsule-rbac-bootstrap]"') == 2
    assert panel.count('hx-swap="outerHTML"') == 2
    assert panel.count('hx-disabled-elt="button"') == 2
    assert panel.count('name="csrf_token"') == 2
    assert 'name="confirm_cluster_rbac"' in panel
    assert 'value="approved"' in panel
    assert "{% include 'components/operation_feedback_oob.html' %}" in panel
    assert "{% include 'components/operational_toast.html' %}" in feedback_oob
    assert 'toast_oob=true' in feedback_oob
    assert 'data-operational-toast' in toast
    assert 'data-operational-toast-close' in toast


def _render_capsule_rbac_panel(snapshot: dict | None, *, can_manage: bool = True) -> str:
    templates = Environment(
        loader=FileSystemLoader(str(ROOT / 'app/templates')),
        autoescape=True,
    )
    template = templates.get_template(
        'integrations/orchestration/container_orchestrator/providers/kubernetes/partials/_capsule_rbac_bootstrap.html'
    )
    permissions = {'clusters.sync', 'clusters.manage', 'integrations.manage'} if can_manage else {'clusters.sync'}
    return template.render(
        capsule_rbac_bootstrap=snapshot,
        cluster=SimpleNamespace(id='cluster-a', name='Kubernetes X300'),
        current_user=SimpleNamespace(has_permission=lambda permission: permission in permissions),
        url_for=lambda endpoint, **kwargs: (
            f'/integrations/kubernetes/{kwargs["cluster_id"]}/capsule-rbac/bootstrap'
            if endpoint == 'integrations.kubernetes_capsule_rbac_bootstrap'
            else f'/test/{endpoint}'
        ),
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
    ready_roles = [
        _role('ready', name=f'kaori-tenant-{profile}-v1')
        for profile in ('viewer', 'operator', 'tenant-admin', 'deployer')
    ]
    html = _render_capsule_rbac_panel(_snapshot('ready', ready_roles))

    assert 'Cluster RBAC prerequisites ready' in html
    assert '4 versioned roles' in html
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
    role_names = ('viewer', 'operator', 'tenant-admin', 'deployer')
    roles = [
        _role('missing' if profile == 'operator' else 'ready', name=f'kaori-tenant-{profile}-v1')
        for profile in role_names
    ]
    snapshot = _snapshot('missing', roles)
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
def test_capsule_rbac_blocked_states_never_offer_bootstrap(status: str, roles: list[dict], expected: str) -> None:
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


def test_capsule_rbac_incomplete_role_evidence_never_claims_ready_or_offers_bootstrap() -> None:
    ready_incomplete = _render_capsule_rbac_panel(_snapshot('ready', [_role('ready')]))
    assert 'Cluster RBAC prerequisites ready' not in ready_incomplete
    assert 'Bootstrap Missing Roles' not in ready_incomplete

    missing_incomplete = _render_capsule_rbac_panel(_snapshot('missing', [_role('missing')]))
    assert 'Bootstrap Missing Roles' not in missing_incomplete
    assert 'name="confirm_cluster_rbac"' not in missing_incomplete


def _disclosure_opening_tag(html: str) -> str:
    marker = html.index('data-capsule-rbac-disclosure')
    start = html.rfind('<details', 0, marker)
    return html[start : html.index('>', marker) + 1]


def test_capsule_rbac_disclosure_is_compact_when_ready_and_open_when_attention_is_required() -> None:
    ready_roles = [
        _role('ready', name=f'kaori-tenant-{profile}-v1')
        for profile in ('viewer', 'operator', 'tenant-admin', 'deployer')
    ]
    ready_html = _render_capsule_rbac_panel(_snapshot('ready', ready_roles))

    assert ' open' not in _disclosure_opening_tag(ready_html)
    assert 'Show Details' in ready_html
    assert 'Hide Details' in ready_html
    assert '4 Ready · 0 Missing · 0 Conflicts' in ready_html
    assert ready_html.count('<details') == 5
    assert 'Cluster RBAC prerequisites ready' in ready_html
    assert 'Review Access Grants' in ready_html
    assert 'Check RBAC' in ready_html
    assert ready_html.index('Check RBAC') < ready_html.index('data-capsule-rbac-disclosure')
    assert 'hx-target="closest [data-capsule-rbac-bootstrap]"' in ready_html
    assert "{% include 'components/operation_feedback_oob.html' %}" in read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/'
        '_capsule_rbac_bootstrap.html'
    )

    missing_roles = ready_roles.copy()
    missing_roles[0] = _role('missing')
    conflict_roles = ready_roles.copy()
    conflict_roles[0] = _role('conflict', reason='Permissions differ')
    for snapshot in (
        None,
        _snapshot('missing', missing_roles),
        _snapshot('conflict', conflict_roles),
        _snapshot('failed', [_role('missing')]),
        _snapshot('ready', [_role('ready')]),
    ):
        html = _render_capsule_rbac_panel(snapshot)
        assert ' open' in _disclosure_opening_tag(html)
        assert 'Show Details' in html
        assert 'Hide Details' in html

    missing_html = _render_capsule_rbac_panel(_snapshot('missing', missing_roles))
    assert 'Bootstrap Missing Roles' in missing_html
    assert 'name="confirm_cluster_rbac"' in missing_html
    assert 'required' in missing_html
    conflict_html = _render_capsule_rbac_panel(_snapshot('conflict', conflict_roles))
    assert 'Bootstrap blocked by a role conflict' in conflict_html
    assert 'Bootstrap Missing Roles' not in conflict_html


def test_capsule_rbac_summary_is_positioned_before_long_capability_registry() -> None:
    detail = read('app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/detail.html')
    validation = detail.split('id="kubernetes-panel-validation"', 1)[1].split('id="kubernetes-panel-runtime"', 1)[0]
    assert validation.count('_capsule_rbac_bootstrap.html') == 1
    assert validation.count('_capability_workspace.html') == 1
    assert validation.index('_capsule_rbac_bootstrap.html') < validation.index('_capability_workspace.html')
    assert 'class="mt-5"' in validation

    capsule = read(
        'app/templates/integrations/orchestration/container_orchestrator/providers/kubernetes/partials/'
        '_capsule_rbac_bootstrap.html'
    )
    assert 'data-capsule-rbac-disclosure' in capsule
    assert '{% if not is_ready %}open{% endif %}' in capsule
    assert '<summary class="flex cursor-pointer list-none' in capsule
    assert 'group-open:hidden' in capsule
    assert 'group-open:inline' in capsule
    assert 'focus-visible:ring-outline-focus' in capsule
    assert 'hx-target="closest [data-capsule-rbac-bootstrap]"' in capsule
