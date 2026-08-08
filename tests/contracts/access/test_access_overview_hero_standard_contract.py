from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_access_overview_hero_uses_shared_kaori_hero_contract() -> None:
    template = read('app/templates/access/overview/index.html')
    assert 'page_hero.shell_classes()' in template
    assert 'page_hero.layout_classes()' in template
    assert "page_hero.intro('shield-check', 'Access', 'users-round')" in template
    assert 'page_hero.context_panel_classes()' in template
    assert 'page_hero.context_status_badge' in template
    assert 'page_hero.context_metric' in template
    assert 'metric.description' in template
    assert 'page_hero.context_info' in template
    assert 'Access Posture' in template
    assert 'Permission Scoped' in template
    assert 'Access changes remain governed inside each workspace.' in template


def test_access_overview_hero_summary_is_permission_aware() -> None:
    presentation = read('app/access/overview/presentation.py')
    for permission in (
        "_can('users.view')",
        "_can('users.manage')",
        "_can('roles.view')",
        "_can('settings.view_operational_activity')",
    ):
        assert permission in presentation
    assert "'hero_metrics': hero_metrics" in presentation
    assert "'label': 'Workspaces'" in presentation
    assert "'description': 'Visible access domains'" in presentation
    assert 'secondary_posture = next(iter(posture_candidates), None)' in presentation
    assert "'Active Users': 'Enabled account identities'" in presentation
    assert "'Providers': 'Enabled identity sources'" in presentation
    assert "'Active Roles': 'Enabled authorization roles'" in presentation
    assert "'Audit Scope': 'Administrative evidence scope'" in presentation


def test_access_overview_ui_remains_open_for_child_page_review() -> None:
    readme = read('app/access/README.md')
    assert 'not the Access UI Final Lock' in readme
    assert 'reviewed independently' in readme
