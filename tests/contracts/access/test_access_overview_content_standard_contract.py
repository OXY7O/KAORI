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


def test_access_overview_workspace_metrics_are_operational_and_domain_owned() -> None:
    presentation = read('app/access/overview/presentation.py')
    for token in (
        "'Active Users'",
        "'External Users'",
        "'Super Admins'",
        "'Identity Links'",
        "'System Roles'",
        "'Custom Roles'",
        "'Assigned'",
        "'Events · 24H'",
        "'Attention · 24H'",
    ):
        assert token in presentation
    for model in ('ExternalIdentityLink', 'Notification', 'RolePermission'):
        assert model in presentation
    assert "Notification.status.in_(['warning', 'error'])" in presentation
    assert "User.auth_source != 'database'" in presentation


def test_access_overview_balances_five_workspace_cards_without_empty_quadrant() -> None:
    presentation = read('app/access/overview/presentation.py')
    assert 'def _workspace_grid_classes(workspace_count: int, index: int)' in presentation
    assert "if workspace_count == 5:" in presentation
    assert "'xl:col-span-2' if index < 3 else 'xl:col-span-3'" in presentation
    assert "workspace['grid_classes'] = _workspace_grid_classes(workspace_count, index)" in presentation


def test_access_overview_explains_permission_scoped_control_boundaries() -> None:
    template = read('app/templates/access/overview/index.html')
    presentation = read('app/access/overview/presentation.py')
    assert "'Access Boundaries'" in template
    assert 'Identity, authentication, authorization, and audit remain separate control responsibilities.' in template
    for boundary in (
        'Identity Lifecycle',
        'Authentication Sources',
        'Authorization Policy',
        'Audit Evidence',
    ):
        assert boundary in presentation
    assert "'boundaries': boundaries" in presentation
