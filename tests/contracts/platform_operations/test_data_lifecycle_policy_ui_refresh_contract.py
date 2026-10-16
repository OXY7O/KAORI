from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_policy_save_refreshes_committed_hero_sidebar_and_detail() -> None:
    routes = (ROOT / 'app/platform_operations/data_lifecycle/routes.py').read_text(encoding='utf-8')
    index = (ROOT / 'app/templates/platform_operations/data_lifecycle/index.html').read_text(encoding='utf-8')
    detail = (ROOT / 'app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html').read_text(
        encoding='utf-8'
    )
    save = routes.split('def save_policy()', 1)[1].split('def run()', 1)[0]
    assert "render_template('platform_operations/data_lifecycle/index.html'" in save
    assert 'lifecycle=_context(feedback=feedback)' in save
    assert 'id="data-lifecycle-page"' in index
    assert 'lifecycle.enabled_domain_count' in index
    assert 'domain.hot_retention_days' in index
    assert 'hx-target="#data-lifecycle-page"' in detail
    assert 'hx-select="#data-lifecycle-page"' in detail
    assert 'hx-swap="outerHTML"' in detail


def test_manual_run_and_preview_keep_targeted_partial_replacement() -> None:
    detail = (ROOT / 'app/templates/platform_operations/data_lifecycle/partials/_domain_workspace.html').read_text(
        encoding='utf-8'
    )
    assert detail.count('hx-target="#data-lifecycle-domain-workspace"') >= 3
