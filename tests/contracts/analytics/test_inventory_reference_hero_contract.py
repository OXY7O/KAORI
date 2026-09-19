from pathlib import Path

ANALYTICS_HERO_FILES = [
    Path('app/templates/kubernetes/analytics/utilization/partials/_hero.html'),
    Path('app/templates/kubernetes/analytics/capacity/partials/_hero.html'),
    Path('app/templates/kubernetes/analytics/storage/partials/_hero.html'),
    Path('app/templates/kubernetes/analytics/workload/partials/_hero.html'),
    Path('app/templates/kubernetes/analytics/top_consumers/partials/_hero.html'),
    Path('app/templates/kubernetes/analytics/alerts/partials/_hero.html'),
    Path('app/templates/kubernetes/analytics/forecast/partials/_hero.html'),
]


def test_analytics_heroes_use_inventory_context_card_contract():
    for path in ANALYTICS_HERO_FILES:
        template = path.read_text()
        assert 'page_hero.context_card(' in template, path
        assert 'context_posture_header(' not in template, path
        assert 'context_panel_classes()' not in template, path
        assert 'analytics/components/_hero_context.html' not in template, path
        assert 'value_classes=' not in template, path
        assert 'text-2xl' not in template, path
        assert 'text-3xl' not in template, path
        assert template.count('page_hero.meta_label(') <= 4, path  # three normal labels plus one blocker branch label


def test_overview_lazy_posture_uses_same_context_card_body():
    posture = Path('app/templates/kubernetes/analytics/overview/partials/_hero_posture.html').read_text()
    loading = Path('app/templates/kubernetes/analytics/overview/partials/_hero_posture_loading.html').read_text()
    assert 'page_hero.context_card_body(' in posture
    assert 'page_hero.context_card_body(' in loading
    assert 'context_panel_classes()' not in posture
    assert 'context_metric(' not in posture


def test_shared_context_card_owns_inventory_metric_scale_and_action():
    shared = Path('app/templates/components/page_hero.html').read_text()
    assert 'macro context_card_body' in shared
    assert 'metrics[:2]' in shared
    assert 'text-lg font-semibold leading-6' in shared
    assert "action_icon='server-cog'" in shared


def test_analytics_hero_helper_is_removed():
    assert not Path('app/templates/analytics/components/_hero_context.html').exists()


def test_blocked_posture_uses_shared_readiness_summary_contract() -> None:
    template = Path('app/templates/kubernetes/analytics/components/_blocked_posture.html').read_text()
    assert 'page_hero.blocked_context_body(' in template
    assert "'Analytics Readiness'" in template
    assert "'Active Scope'" in template
    assert "'Missing Evidence'" in template
    assert "'Current Step'" not in template
    assert "'Progress'" not in template


def test_storage_and_capacity_hero_helpers_are_concise_and_semantic() -> None:
    storage = Path('app/templates/kubernetes/analytics/storage/partials/_hero.html').read_text()
    capacity = Path('app/templates/kubernetes/analytics/capacity/partials/_hero.html').read_text()

    assert "('server', 'Node Pressure'" in storage
    assert "'Node filesystem'" in storage
    assert 'filesystem.highest_node|default' not in storage
    assert 'truncate(30' not in storage
    assert "'Ready-Worker capacity'" in capacity
    assert 'Tightest Ready-worker scheduling margin' not in capacity
