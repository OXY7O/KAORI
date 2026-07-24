from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_welcome_catalog_matches_current_navigation_domains() -> None:
    shortcuts = (ROOT / 'app/welcome/shortcuts.py').read_text()

    for title in (
        'Dashboards',
        'K8s Inventory',
        'K8s Analytics',
        'Intelligence',
        'Integrations',
        'K8s Operations',
        'Platform Operations',
        'K8s Governance',
        'Reports',
        'Access',
        'Settings',
    ):
        assert f"'title': '{title}'" in shortcuts

    assert "'title': 'Kubernetes Cluster'" not in shortcuts
    assert "('jobs.view', 'integrations.jobs')" in shortcuts
    assert "('settings.manage_integrations', 'settings.inventory_sync.index')" in shortcuts


def test_welcome_title_case_and_hero_note_contract() -> None:
    template = (ROOT / 'app/templates/welcome/index.html').read_text()
    hero = (ROOT / 'app/templates/components/page_hero.html').read_text()

    assert 'placeholder="Search Workspace"' in template
    assert '{{ current_user.role_display_name }} Access' in template
    assert '>Available</span>' in template
    assert 'Open The Capability You Need' in template
    assert '<strong>Open Workspace</strong>' in template
    assert 'Only workspaces permitted for your current role are displayed.' in template
    assert '<p class="{{ context_metric_description_classes() }}">{{ text }}</p>' in hero
