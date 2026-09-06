from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

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


def test_kubernetes_analytics_heroes_use_shared_three_slot_metadata_renderer() -> None:
    base = ROOT / 'app' / 'templates' / 'kubernetes' / 'analytics'
    drifted: list[str] = []

    for relative in KUBERNETES_ANALYTICS_HEROES:
        source = (base / relative).read_text(encoding='utf-8')
        if 'page_hero.analytics_metadata(' not in source or 'page_hero.metadata_row_classes()' in source:
            drifted.append(relative)

    assert not drifted, f'Analytics Hero metadata still bypasses the shared renderer: {drifted}'


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


def test_global_hero_verifier_accepts_shared_analytics_metadata_contract() -> None:
    namespace = runpy.run_path(str(ROOT / 'scripts' / 'verify_hero_component_standard.py'))
    namespace['verify']()
