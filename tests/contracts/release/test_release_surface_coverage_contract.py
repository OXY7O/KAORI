from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from release_surface_registry import SURFACES, blueprint_vars, navigation_endpoints  # noqa: E402
from verify_final_release import SHORT_LABELS  # noqa: E402


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_release_registry_closes_navigation_and_blueprint_inventory() -> None:
    assert len(navigation_endpoints()) == 60
    assert len(set(navigation_endpoints())) == 60
    assert len(blueprint_vars()) == 25
    assert len(set(blueprint_vars())) == 25
    assert len(SURFACES) == 16

    assert {surface.lock_state for surface in SURFACES} == {'LOCKED', 'BASELINE LOCKED', 'SYSTEM LOCKED'}
    assert next(surface for surface in SURFACES if surface.key == 'intelligence').lock_state == 'BASELINE LOCKED'
    assert next(surface for surface in SURFACES if surface.key == 'health').lock_state == 'SYSTEM LOCKED'


def test_general_release_titles_stay_short() -> None:
    assert set(SHORT_LABELS) == {surface.title for surface in SURFACES}
    assert all(len(label) <= 18 for label in SHORT_LABELS.values())
    assert all('Final Lock' not in label and 'Baseline Lock' not in label for label in SHORT_LABELS.values())
    assert SHORT_LABELS['Analytics'] == 'Analytics'
    assert SHORT_LABELS['Platform Operations'] == 'Platform Ops'
    assert SHORT_LABELS['Notification Center'] == 'Notifications'


def test_general_release_runner_owns_short_pass_and_detailed_fail_contract() -> None:
    runner = read('scripts/verify_final_release.py')
    assert "print(f'PASS — KAORI {label}')" in runner
    assert "print(f'FAIL — KAORI {label}')" in runner
    assert "print('PASS — KAORI Final Release')" in runner
    assert 'capture_output=True' in runner
    assert "('Static Quality', ('bash', 'scripts/quality_gate.sh', '--static'))" in runner
    assert "('Test Suite', ('bash', 'scripts/quality_gate.sh', '--tests'))" in runner
    assert "('Frontend', ('bash', 'scripts/quality_gate.sh', '--frontend'))" in runner


def test_quality_gate_cannot_skip_surface_coverage() -> None:
    quality_gate = read('scripts/quality_gate.sh')
    assert 'python scripts/verify_release_surface_coverage.py' in quality_gate
    assert quality_gate.index('python scripts/verify_release_surface_coverage.py') < quality_gate.index(
        'python scripts/verify_welcome_final_lock.py'
    )


def test_cluster_listing_legacy_chain_is_retired_and_guarded() -> None:
    coverage = read('scripts/verify_release_surface_coverage.py')
    sidebar = read('app/templates/components/navigation/sidebar.html')
    kubernetes_registration = read(
        'app/integrations/orchestration/container_orchestrator/adapters/kubernetes_api/__init__.py'
    )

    assert 'can_clusters' not in sidebar
    assert "navigation_endpoint_prefixes=('integrations.kubernetes', 'cluster.')" in kubernetes_registration
    assert 'cluster.list_clusters' not in ''.join(
        path.read_text(encoding='utf-8') for path in (ROOT / 'app/templates').rglob('*.html')
    )

    for relative in (
        'app/templates/cluster/index.html',
        'app/templates/cluster/partials/_delete_modal.html',
        'app/templates/cluster/partials/_inventory_badge.html',
        'app/templates/cluster/partials/_loading_bar.html',
        'app/templates/cluster/partials/_pagination.html',
        'app/templates/cluster/partials/_status_badge.html',
        'app/templates/cluster/partials/_table.html',
    ):
        assert not (ROOT / relative).exists()
        assert relative in coverage


def test_release_coverage_documentation_keeps_explicit_incomplete_feature_state() -> None:
    documentation = read('docs/architecture/RELEASE_SURFACE_COVERAGE.md')
    for token in (
        '60 navigation links',
        '25 registered blueprints',
        'Intelligence | BASELINE LOCKED',
        'Runtime Health | SYSTEM LOCKED',
        'Cluster Management is intentionally not a separate sidebar menu',
        'PASS is short; FAIL is detailed.',
    ):
        assert token in documentation
