from pathlib import Path


HERO_TEMPLATES = [
    'app/templates/analytics/utilization/partials/_hero.html',
    'app/templates/analytics/capacity/partials/_hero.html',
    'app/templates/analytics/storage/partials/_hero.html',
    'app/templates/analytics/workload/partials/_hero.html',
    'app/templates/analytics/top_consumers/partials/_hero.html',
    'app/templates/analytics/alerts/partials/_hero.html',
    'app/templates/analytics/forecast/index.html',
    'app/templates/analytics/overview/partials/_hero_posture.html',
]


def test_all_analytics_heroes_use_shared_manage_clusters_action():
    for template_path in HERO_TEMPLATES:
        template = Path(template_path).read_text()
        assert 'analytics/components/_hero_context.html' in template
        assert 'analytics_hero.manage_clusters_action()' in template


def test_blocked_posture_keeps_manage_clusters_recovery_action():
    template = Path('app/templates/analytics/components/_blocked_posture.html').read_text()
    assert 'analytics_hero.manage_clusters_action()' in template


def test_analytics_manage_clusters_action_targets_kubernetes_integrations():
    template = Path('app/templates/analytics/components/_hero_context.html').read_text()
    assert "url_for('integrations.kubernetes')" in template
    assert 'Manage Clusters' in template
    assert 'page_hero.context_single_action_classes()' in template
