from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = ROOT / 'app' / 'templates' / 'kubernetes' / 'analytics' / 'overview' / 'partials' / '_health_summary.html'
SHARED_CONTROLS_PATH = ROOT / 'app' / 'templates' / 'analytics' / 'components' / '_controls_readiness.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
COPIED_SHELL = 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm'
SHARED_SHELL = 'class="{{ overview_surface.snapshot_shell_classes() }}"'


def test_overview_health_summary_uses_shared_snapshot_shell_authority() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')
    shared_controls = SHARED_CONTROLS_PATH.read_text(encoding='utf-8')

    assert '{% import "analytics/components/_analysis_surfaces.html" as overview_surface %}' in source
    assert '{% import "analytics/components/_controls_readiness.html" as shared_readiness %}' in source
    # Controls/readiness are owned by a shared adapter; the health summary
    # retains exactly one page-local snapshot shell. Avoid duplicating either.
    assert source.count(SHARED_SHELL) == 1
    assert 'shared_readiness.frame(' in source
    assert 'shared_readiness.controls_grid()' in source
    assert 'shared_readiness.readiness_grid()' in source
    assert 'shared_readiness.snapshot_card(' in source
    assert 'components/table_primitives.html' in shared_controls
    assert COPIED_SHELL not in source
    assert COPIED_SHELL not in shared_controls

    assert 'id="analytics-overview-filter"' in source
    assert 'data-overview-refresh-request="true"' in source
    assert 'hx-target="#analytics-overview-page"' in source
    assert 'hx-select="#analytics-overview-page"' in source
    assert 'hx-swap="outerHTML"' in source
    assert 'hx-push-url="true"' in source
    assert 'hx-indicator="#analytics-overview-refresh-indicator"' in source
    assert 'hx-sync="#analytics-overview-filter:replace"' in source
    assert 'Analytics Controls & Data Readiness' in source
    assert 'Operational Health Summary' in source
    assert '6 Health Signals' in source
    assert 'Recommended Review Path' in source
    assert 'sm:grid-cols-2 lg:grid-cols-3' in source


def test_overview_health_summary_copied_shell_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
