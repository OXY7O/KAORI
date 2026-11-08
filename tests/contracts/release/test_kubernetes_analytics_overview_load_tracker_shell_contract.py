from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = ROOT / 'app' / 'templates' / 'kubernetes' / 'analytics' / 'overview' / 'partials' / '_load_tracker.html'
SHARED_TRACKER_PATH = ROOT / 'app' / 'templates' / 'analytics' / 'components' / '_section_load_tracker.html'
BASELINE_PATH = ROOT / 'docs' / 'architecture' / 'ui-style-debt-baseline.json'
COPIED_SHELL = 'overflow-hidden rounded-xl border border-outline-default bg-surface-card shadow-sm'


def test_overview_load_tracker_uses_shared_snapshot_shell_authority() -> None:
    source = TARGET_PATH.read_text(encoding='utf-8')
    shared_tracker = SHARED_TRACKER_PATH.read_text(encoding='utf-8')

    # The overview delegates its loading state to the approved shared
    # implementation; assertions must follow ownership rather than requiring
    # a duplicate page-local tracker.
    assert '{% import "analytics/components/_section_load_tracker.html" as section_tracker %}' in source
    assert 'section_tracker.render("analytics-overview-load-tracker")' in source
    assert '{% import "analytics/components/_analysis_surfaces.html" as analysis_surface %}' in shared_tracker
    assert 'id="{{ tracker_id }}"' in shared_tracker
    assert (
        'class="hidden {{ analysis_surface.snapshot_shell_classes() }} px-4 py-3 shadow-sm sm:px-5"'
        not in shared_tracker
    )
    assert 'class="hidden {{ analysis_surface.snapshot_shell_classes() }} px-4 py-3 sm:px-5"' in shared_tracker
    assert COPIED_SHELL not in source
    assert COPIED_SHELL not in shared_tracker

    for marker in (
        'data-overview-load-tracker="true"',
        'data-overview-load-state="idle"',
        'role="status"',
        'aria-live="polite"',
        'data-overview-load-title',
        'data-overview-load-description',
        'data-overview-load-counter',
        'data-overview-load-progress',
        'Loading Analytics Overview',
        'Preparing committed analytics snapshots.',
        '0/0 Sections',
        'sm:flex-row sm:items-center sm:justify-between',
    ):
        assert marker in shared_tracker


def test_overview_load_tracker_copied_shell_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload['files']
