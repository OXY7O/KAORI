from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = ROOT / 'app' / 'templates' / 'kubernetes' / 'analytics' / 'overview' / 'partials' / '_health_summary.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
COPIED_SHELL = 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm'
SHARED_SHELL = 'class="{{ overview_surface.snapshot_shell_classes() }}"'


def test_overview_health_summary_uses_shared_snapshot_shell_authority() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    assert '{% import "analytics/components/_analysis_surfaces.html" as overview_surface %}' in source
    assert source.count(SHARED_SHELL) == 2
    assert COPIED_SHELL not in source

    assert 'id="analytics-overview-filter"' in source
    assert 'data-overview-refresh-request="true"' in source
    assert 'hx-target="#analytics-overview-page"' in source
    assert 'hx-select="#analytics-overview-page"' in source
    assert 'hx-swap="outerHTML"' in source
    assert 'hx-push-url="true"' in source
    assert 'hx-indicator="#analytics-overview-refresh-indicator"' in source
    assert 'hx-sync="#analytics-overview-filter:replace"' in source
    assert 'data-analytics-controls-readiness' in source
    assert 'Analytics Controls &amp; Data Readiness' in source
    assert 'Operational Health Summary' in source
    assert '6 Health Signals' in source
    assert 'Recommended Review Path' in source
    assert 'sm:grid-cols-2 lg:grid-cols-3' in source


def test_overview_health_summary_copied_shell_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
