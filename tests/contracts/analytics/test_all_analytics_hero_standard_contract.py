from pathlib import Path

HERO_TEMPLATES = [
    Path('app/templates/analytics/overview/partials/_hero.html'),
    Path('app/templates/analytics/utilization/partials/_hero.html'),
    Path('app/templates/analytics/capacity/partials/_hero.html'),
    Path('app/templates/analytics/storage/partials/_hero.html'),
    Path('app/templates/analytics/workload/partials/_hero.html'),
    Path('app/templates/analytics/top_consumers/partials/_hero.html'),
    Path('app/templates/analytics/alerts/partials/_hero.html'),
    Path('app/templates/analytics/forecast/index.html'),
]


def test_analytics_heroes_cap_metadata_to_three_labels():
    for path in HERO_TEMPLATES:
        template = path.read_text()
        # Count the largest non-blocked branch conservatively by total literal calls.
        # Dependency labels are mutually exclusive with normal metadata.
        normal_calls = [
            line for line in template.splitlines() if 'page_hero.meta_label' in line and 'lock-keyhole' not in line
        ]
        assert len(normal_calls) <= 3, f'{path} has {len(normal_calls)} normal metadata labels'


def test_all_domain_heroes_use_manage_clusters_and_two_metric_maximum():
    domain_heroes = HERO_TEMPLATES[1:]
    for path in domain_heroes:
        template = path.read_text()
        assert 'manage_clusters_action()' in template or "url_for('integrations.kubernetes')" in template
        assert template.count('page_hero.context_metric(') <= 2
        assert 'context_bottom_notice(' not in template


def test_hero_helpers_do_not_truncate_technical_identifiers():
    for path in HERO_TEMPLATES:
        template = path.read_text()
        assert '|truncate(' not in template
