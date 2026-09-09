from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = ROOT / 'app' / 'templates' / 'kubernetes' / 'analytics' / 'overview' / 'index.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
COPIED_SHELL = 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm'


def test_overview_workspace_uses_shared_snapshot_shell_authority() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    assert '{% import "analytics/components/_analysis_surfaces.html" as analysis_surface %}' in source
    assert 'id="analytics-overview-workspace"' in source
    assert 'class="{{ analysis_surface.snapshot_shell_classes() }}"' in source
    assert COPIED_SHELL not in source

    assert 'data-analytics-tabset' in source
    assert 'data-analytics-tabset-id="overview-content"' in source
    assert 'data-default-tab="utilization"' in source
    assert "content_tabs.render_buttons('overview-content', overview_tabs" in source
    assert 'role="tabpanel"' in source
    assert 'aria-labelledby="overview-content-tab-{{ tab_id }}"' in source
    assert 'data-overview-lazy-section="true"' in source
    assert 'hx-trigger="kaori:analytics-tab-activated once"' in source
    assert 'class="p-4 sm:p-5"' in source


def test_overview_workspace_copied_shell_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
