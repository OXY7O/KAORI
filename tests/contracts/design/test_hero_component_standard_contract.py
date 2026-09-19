from __future__ import annotations

import re
import runpy
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

KUBERNETES_ANALYTICS_HEROES = (
    'overview/partials/_hero.html',
    'utilization/partials/_hero.html',
    'capacity/partials/_hero.html',
    'storage/partials/_hero.html',
    'workload/partials/_hero.html',
    'top_consumers/partials/_hero.html',
    'alerts/partials/_hero.html',
    'forecast/partials/_hero.html',
)


def test_hero_component_standard_is_enforced() -> None:
    result = subprocess.run(
        [sys.executable, 'scripts/verify_hero_component_standard.py'],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert 'KAORI Hero component standard passed' in result.stdout


def test_unmanaged_hero_detector_scopes_brand_surface_to_shell_container() -> None:
    namespace = runpy.run_path(str(ROOT / 'scripts' / 'verify_hero_component_standard.py'))
    detector = namespace['_has_unmanaged_hero_shell']

    normal_page = '<main><h1>Account</h1><a class="bg-kaori-primary">Save</a></main>'
    unmanaged_hero = '<section class="bg-kaori-primary rounded-2xl"><h1>Local Hero</h1></section>'

    assert detector(normal_page) is False
    assert detector(unmanaged_hero) is True


def test_hero_documentation_has_one_global_contract_and_one_domain_extension() -> None:
    components = ROOT / 'docs' / 'design' / 'components'
    global_standard = (components / 'HERO.md').read_text(encoding='utf-8')
    analytics_extension = (components / 'ANALYTICS_HERO.md').read_text(encoding='utf-8')

    assert 'KAORI Hero Component Standard v1.7' in global_standard
    assert 'Hero Profile' in global_standard
    assert 'Hero State' in global_standard
    assert 'same Profile + same State' in global_standard
    assert 'exactly three metadata' in global_standard
    assert 'normal, blocked, and degraded' in global_standard
    assert '89–96 character' in global_standard
    assert '10–11 words' in global_standard
    assert '16 px, regular, 28 px line height' in global_standard
    assert 'Action Icon Box' in global_standard
    assert 'Context Icon Box' in global_standard
    assert 'Status Badge Box' in global_standard
    assert 'exactly two compact metrics' in global_standard
    assert 'kaori-hero-shell' in global_standard
    assert 'components/DARK_MODE.md' in global_standard
    assert 'Kubernetes Analytics Hero Extension' in analytics_extension
    assert 'Blocked Analytics metadata remains exactly three items' in analytics_extension
    assert 'page_hero.analytics_metadata(...)' in analytics_extension
    assert not (components / 'ANALYTICS_HERO_STANDARD.md').exists()
    assert not (components / 'ANALYTICS_HERO_INVENTORY_REFERENCE.md').exists()


def test_operational_dashboard_uses_one_canonical_hero_profile() -> None:
    component = (ROOT / 'app' / 'templates' / 'components' / 'page_hero.html').read_text(encoding='utf-8')
    kubernetes = (ROOT / 'app' / 'templates' / 'kubernetes' / 'dashboard' / 'partials' / '_hero.html').read_text(
        encoding='utf-8'
    )
    object_storage = (
        ROOT / 'app' / 'templates' / 'storage' / 'object_storage' / 'dashboard' / 'partials' / '_hero.html'
    ).read_text(encoding='utf-8')

    assert 'macro operational_dashboard(' in component
    assert 'macro persistent_metadata(' in component
    assert 'data-kaori-hero-metadata-policy="persistent"' in component
    assert 'page_hero.operational_dashboard(' in kubernetes
    assert 'page_hero.operational_dashboard(' in object_storage
    for source in (kubernetes, object_storage):
        assert 'page_hero.shell_classes()' not in source
        assert 'page_hero.layout_classes()' not in source
        assert 'page_hero.context_panel_classes()' not in source


def test_blocked_hero_context_has_one_shared_renderer() -> None:
    component = (ROOT / 'app' / 'templates' / 'components' / 'page_hero.html').read_text(encoding='utf-8')
    kubernetes = (ROOT / 'app' / 'templates' / 'components' / 'cluster' / '_hero_blocked_context.html').read_text(
        encoding='utf-8'
    )
    object_storage = (
        ROOT
        / 'app'
        / 'templates'
        / 'storage'
        / 'object_storage'
        / 'inventory'
        / 'components'
        / '_hero_blocked_context.html'
    ).read_text(encoding='utf-8')

    assert 'macro blocked_context_body(' in component
    assert 'page_hero.blocked_context_body(' in kubernetes
    assert 'page_hero.blocked_context_body(' in object_storage


def test_kubernetes_analytics_heroes_use_three_stable_metadata_slots_in_all_states() -> None:
    component = (ROOT / 'app' / 'templates' / 'components' / 'page_hero.html').read_text(encoding='utf-8')
    assert 'macro analytics_metadata(' in component
    assert 'data-kaori-analytics-metadata' in component
    assert 'persistent_metadata(analytics_items)' in component

    base = ROOT / 'app' / 'templates' / 'kubernetes' / 'analytics'
    for relative in KUBERNETES_ANALYTICS_HEROES:
        source = (base / relative).read_text(encoding='utf-8')
        assert 'page_hero.analytics_metadata(' in source, relative
        assert 'page_hero.metadata_row_classes()' not in source, relative


def test_object_storage_analytics_uses_three_stable_metadata_slots_in_all_states() -> None:
    source = (
        ROOT / 'app' / 'templates' / 'storage' / 'object_storage' / 'analytics' / 'partials' / '_hero.html'
    ).read_text(encoding='utf-8')

    assert 'page_hero.analytics_metadata(' in source
    assert 'page_hero.metadata_row_classes()' not in source
    assert re.search(r"evidence_label\s*=\s*['\"]Committed Snapshot Boundary['\"]", source)
    assert '{% if inventory_observed_at %}' not in source


def test_object_storage_inventory_setup_copy_is_concise() -> None:
    source = (
        ROOT
        / 'app'
        / 'templates'
        / 'storage'
        / 'object_storage'
        / 'inventory'
        / 'components'
        / '_onboarding_banner.html'
    ).read_text(encoding='utf-8')

    assert 'Register a Storage integration before KAORI collects object-storage snapshots.' in source
    assert 'before KAORI can collect and present committed object-storage systems' not in source


def test_kubernetes_analytics_cluster_remediation_uses_integration_action() -> None:
    source = (ROOT / 'app' / 'common' / 'dependencies.py').read_text(encoding='utf-8')
    start = source.index('def cluster_required_blocker()')
    end = source.index('\n\ndef metrics_source_setup_blocker', start)
    blocker = source[start:end]

    assert "'action_label': 'Open Cluster Integrations'" in blocker
    assert "'action_url': url_for('integrations.kubernetes')" in blocker
    assert "'permission': 'clusters.manage'" in blocker
    assert "'action_label': 'Add Cluster'" not in blocker
    assert "'action_label': 'Open Cluster Integration'" not in blocker
    assert "url_for('cluster.add_cluster')" not in blocker


def test_removed_hero_macros_are_absent_from_implementation() -> None:
    source = (ROOT / 'app' / 'templates' / 'components' / 'page_hero.html').read_text(encoding='utf-8')
    for macro in (
        'context_posture_header',
        'context_posture_note',
        'context_bottom_notice',
        'action_group_classes',
        'secondary_action_classes',
        'destructive_action_classes',
        'supporting_strip',
    ):
        assert f'macro {macro}' not in source


def test_hero_right_header_accessories_have_three_canonical_variants() -> None:
    source = (ROOT / 'app' / 'templates' / 'components' / 'page_hero.html').read_text(encoding='utf-8')

    assert 'macro context_action_icon_box(icon, href, aria_label, title=None)' in source
    assert 'macro context_icon_box(icon)' in source
    assert "macro context_header_status(eyebrow_label, title, status_label, status_tone='info')" in source
    assert 'aria-label="{{ aria_label }}"' in source
    assert 'context_status_badge(status_label, status_tone)' in source


def test_hero_context_panel_footer_variants_share_one_precise_row_rhythm() -> None:
    source = (ROOT / 'app' / 'templates' / 'components' / 'page_hero.html').read_text(encoding='utf-8')

    assert 'flex h-full min-h-[13rem] flex-col gap-3' in source
    assert 'grid grid-cols-2 auto-rows-fr gap-2' in source
    assert 'kaori-hero-tile mt-auto flex min-h-10 items-center gap-2' in source
    assert "mt-auto grid min-h-10 gap-2 {{ 'grid-cols-2' if columns == 2 else 'grid-cols-1' }}" in source
    assert 'mt-3 grid grid-cols-2 gap-2' not in source
    assert 'mt-auto grid gap-2 pt-3' not in source
