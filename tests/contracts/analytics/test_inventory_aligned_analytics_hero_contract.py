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


def test_analytics_posture_uses_inventory_title_density_without_description():
    hero_paths = [
        'app/templates/analytics/utilization/partials/_hero.html',
        'app/templates/analytics/capacity/partials/_hero.html',
        'app/templates/analytics/storage/partials/_hero.html',
        'app/templates/analytics/workload/partials/_hero.html',
        'app/templates/analytics/top_consumers/partials/_hero.html',
        'app/templates/analytics/alerts/partials/_hero.html',
        'app/templates/analytics/overview/partials/_hero_posture.html',
        'app/templates/analytics/forecast/index.html',
    ]
    for path in hero_paths:
        content = Path(path).read_text()
        assert 'analytics_hero.posture_description' not in content
        assert 'text-3xl font-bold leading-none text-brand-foreground' not in content
        assert 'text-3xl font-semibold leading-none text-brand-foreground' not in content


def test_storage_hero_uses_concise_primary_pressure_value():
    content = Path('app/templates/analytics/storage/partials/_hero.html').read_text()
    assert "'Highest Node Pressure', ('%.1f%%'" in content
    assert "truncate(30, true, '…')" in content
    assert "filesystem.highest_node ~ ' · '" not in content


def test_storage_hero_uses_semantic_context_instead_of_truncated_node_name():
    template = _read("app/templates/analytics/storage/partials/_hero.html")
    assert "'Node Filesystem' if highest_usage is not none" in template
    assert "filesystem.highest_node|default" not in template
    assert "truncate(30" not in template


def test_capacity_hero_uses_compact_ready_worker_context():
    template = _read("app/templates/analytics/capacity/partials/_hero.html")
    assert "'Ready-Worker Capacity'" in template
    assert "Tightest Ready-worker scheduling margin" not in template
