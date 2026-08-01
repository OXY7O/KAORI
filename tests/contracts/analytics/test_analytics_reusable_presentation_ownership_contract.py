from pathlib import Path


HERO_FILES = [
    'app/templates/analytics/overview/partials/_hero_posture.html',
    'app/templates/analytics/utilization/partials/_hero.html',
    'app/templates/analytics/capacity/partials/_hero.html',
    'app/templates/analytics/storage/partials/_hero.html',
    'app/templates/analytics/workload/partials/_hero.html',
    'app/templates/analytics/top_consumers/partials/_hero.html',
    'app/templates/analytics/alerts/partials/_hero.html',
    'app/templates/analytics/forecast/index.html',
]


def test_page_hero_owns_inventory_aligned_metric_scale():
    template = Path('app/templates/components/page_hero.html').read_text()
    assert 'macro context_posture_header' in template
    assert 'text-lg font-semibold leading-6 text-brand-foreground' in template
    assert 'value_classes or context_metric_value_classes()' in template


def test_every_analytics_hero_uses_shared_posture_and_metric_contracts():
    for filename in HERO_FILES:
        template = Path(filename).read_text()
        assert 'page_hero.context_posture_header(' in template, filename
        assert 'page_hero.context_metric(' in template, filename
        assert 'value_classes=' not in template, filename
        assert 'text-2xl' not in template, filename
        assert 'text-3xl' not in template, filename


def test_analytics_hero_metadata_remains_capped_at_three():
    intro_files = [
        'app/templates/analytics/overview/partials/_hero.html',
        'app/templates/analytics/utilization/partials/_hero.html',
        'app/templates/analytics/capacity/partials/_hero.html',
        'app/templates/analytics/storage/partials/_hero.html',
        'app/templates/analytics/workload/partials/_hero.html',
        'app/templates/analytics/top_consumers/partials/_hero.html',
        'app/templates/analytics/alerts/partials/_hero.html',
        'app/templates/analytics/forecast/index.html',
    ]
    for filename in intro_files:
        template = Path(filename).read_text()
        # Static source can contain both normal and dependency branches. Each branch
        # has one cluster label plus at most two branch-specific labels.
        assert template.count('page_hero.meta_label(') <= 4, filename
