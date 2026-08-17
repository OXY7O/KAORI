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
    assert 'page_hero.context_status_badge(access_overview.overall_status_label' in template
    assert 'page_hero.context_metric' in template
    assert 'metric.description' in template
    assert 'page_hero.context_info' in template
    assert 'Access Posture' in template
    assert 'Permission Scoped' in template
    assert 'access_overview.attention_workspace_count' in template
    assert 'Read-only composition; posture comes from each authoritative Access workspace.' in template


def test_access_overview_hero_summary_is_permission_aware() -> None:
    presentation = read('app/access/overview/presentation.py')
    for permission in (
        "_can('users.view')",
        "_can('users.manage')",
        "_can('roles.view')",
        "_can('settings.view_operational_activity')",
    ):
        assert permission in presentation
    assert "'attention_workspace_count': attention_workspace_count" in presentation
    assert "'unknown_workspace_count': unknown_workspace_count" in presentation
    assert "'overall_status_label': overall_status_label" in presentation
    assert "'overall_status_tone': overall_status_tone" in presentation
    assert "'label': 'Workspaces'" in presentation
    assert "'label': 'Review'" in presentation
    assert "'description': 'Visible access domains'" in presentation
    assert "'description': 'Domains needing review'" in presentation


def test_access_overview_is_protected_by_access_final_lock() -> None:
    readme = read('app/access/README.md')
    assert 'Access v1 is final-locked' in readme
    assert 'verify_access_final_lock.py' in readme
