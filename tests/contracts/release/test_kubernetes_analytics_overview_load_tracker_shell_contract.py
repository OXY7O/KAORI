from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = (
    ROOT
    / 'app'
    / 'templates'
    / 'kubernetes'
    / 'analytics'
    / 'overview'
    / 'partials'
    / '_load_tracker.html'
)
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
COPIED_SHELL = 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm'


def test_overview_load_tracker_uses_shared_snapshot_shell_authority() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')

    assert '{% import "analytics/components/_analysis_surfaces.html" as analysis_surface %}' in source
    assert 'id="analytics-overview-load-tracker"' in source
    assert (
        'class="hidden {{ analysis_surface.snapshot_shell_classes() }} px-4 py-3 shadow-sm sm:px-5"'
        not in source
    )
    assert (
        'class="hidden {{ analysis_surface.snapshot_shell_classes() }} px-4 py-3 sm:px-5"'
        in source
    )
    assert COPIED_SHELL not in source

    assert 'data-overview-load-tracker="true"' in source
    assert 'data-overview-load-state="idle"' in source
    assert 'role="status"' in source
    assert 'aria-live="polite"' in source
    assert 'data-overview-load-title' in source
    assert 'data-overview-load-description' in source
    assert 'data-overview-load-counter' in source
    assert 'data-overview-load-progress' in source
    assert 'Loading Analytics Overview' in source
    assert 'Preparing committed analytics snapshots.' in source
    assert '0/0 Sections' in source
    assert 'sm:flex-row sm:items-center sm:justify-between' in source


def test_overview_load_tracker_copied_shell_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
