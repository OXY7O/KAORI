from __future__ import annotations

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
    app_root = ROOT / 'app'
    python_sources = tuple(app_root.rglob('*.py'))
    new_matches = [
        str(path.relative_to(ROOT))
        for path in python_sources
        if 'Open Cluster Integration' in path.read_text(encoding='utf-8')
    ]
    old_matches = [
        str(path.relative_to(ROOT)) for path in python_sources if 'Add Cluster' in path.read_text(encoding='utf-8')
    ]

    assert new_matches, 'Open Cluster Integration is not configured in application Python sources'
    assert not old_matches, f'Retired Add Cluster remediation remains in: {old_matches}'
