from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_access_overview_workspace_posture_matches_kaori_operational_card_grammar() -> None:
    template = read('app/templates/access/overview/index.html')
    assert '{% import "components/table_label.html" as table_label %}' in template
    assert "'Workspace Posture'" in template
    assert 'table_label.status_indicator_label(access_overview.overall_status_label' in template
    assert 'table_label.status_indicator_label(workspace.status_label, workspace.status_tone)' in template
    assert 'Control {{' in template
    assert 'workspace.metrics' in template
    assert 'workspace.supporting_text' in template
    assert 'workspace.boundary_label' in template
    assert 'grid gap-4 md:grid-cols-2 xl:grid-cols-6' in template
    assert 'workspace.grid_classes' in template


def test_access_overview_composes_domain_owned_posture_contracts() -> None:
    presentation = read('app/access/overview/presentation.py')
    for token in (
        'build_user_access_summary',
        'build_identity_provider_summary',
        'build_roles_index_context',
        'build_permission_registry_snapshot',
        'get_notification_activity_summary',
    ):
        assert token in presentation
    for forbidden in (
        'User.query',
        'IdentityProvider.query',
        'Role.query',
        'Permission.query',
        'Notification.query',
        'db.session',
    ):
        assert forbidden not in presentation
    assert "permission_summary['drift_count']" in presentation
    assert "users['active_super_admins']" in presentation
    user_summary = read('app/users/access_summary.py')
    assert "'unassigned_active_users': unassigned_active_users" in user_summary
    assert "summary['inactive_assigned_users']" in presentation
    assert "activity['attention_24h']" in presentation


def test_access_overview_balances_five_workspace_cards_without_empty_quadrant() -> None:
    presentation = read('app/access/overview/presentation.py')
    assert 'def _workspace_grid_classes(workspace_count: int, index: int)' in presentation
    assert 'if workspace_count == 5:' in presentation
    assert "'xl:col-span-2' if index < 3 else 'xl:col-span-3'" in presentation
    assert "workspace['grid_classes'] = _workspace_grid_classes(workspace_count, index)" in presentation


def test_access_overview_explains_permission_scoped_control_boundaries() -> None:
    template = read('app/templates/access/overview/index.html')
    presentation = read('app/access/overview/presentation.py')
    assert "'Access Boundaries'" in template
    assert (
        'Identity, authentication, authorization, and audit remain separate authorities with their own '
        'posture evidence.' in template
    )
    assert 'table_label.status_indicator_label(boundary.status_label, boundary.status_tone)' in template
    for boundary in (
        'Identity Lifecycle',
        'Authentication Sources',
        'Authorization Policy',
        'Audit Evidence',
    ):
        assert boundary in presentation
    assert "'boundaries': boundaries" in presentation
