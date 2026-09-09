from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TARGET_PATH = (
    ROOT
    / "app"
    / "templates"
    / "kubernetes"
    / "analytics"
    / "partials"
    / "_load_tracker.html"
)
BASELINE_PATH = ROOT / "docs" / "architecture" / "ui-style-debt-baseline.json"
COPIED_SHELL = (
    "overflow-hidden rounded-xl border border-outline-default "
    "bg-surface-card shadow-sm"
)


def test_generic_analytics_load_tracker_uses_shared_snapshot_shell_authority() -> None:
    source = TARGET_PATH.read_text(encoding="utf-8")

    assert (
        '{% import "analytics/components/_analysis_surfaces.html" as analysis_surface %}'
        in source
    )
    assert (
        'class="hidden {{ analysis_surface.snapshot_shell_classes() }} px-5 py-4"'
        in source
    )
    assert COPIED_SHELL not in source

    assert "{% set tracker_id = analytics_tracker_id|default('analytics-load-tracker') %}" in source
    assert "{% set page_id = analytics_page_id|default('analytics-page') %}" in source
    assert 'data-analytics-load-tracker="true"' in source
    assert 'data-analytics-page-id="{{ page_id }}"' in source
    assert 'data-analytics-title="{{ title }}"' in source
    assert 'data-analytics-description="{{ description }}"' in source
    assert 'data-analytics-complete-title="{{ complete_title }}"' in source
    assert 'data-analytics-complete-description="{{ complete_description }}"' in source
    assert 'data-analytics-load-title' in source
    assert 'data-analytics-load-description' in source
    assert 'data-analytics-load-counter' in source
    assert 'data-analytics-load-progress' in source
    assert "sm:flex-row sm:items-center sm:justify-between" in source
    assert "tracker.classList.remove('hidden')" in source
    assert "tracker.classList.add('hidden')" in source
    assert "tracker.dataset.analyticsLoadState = 'complete'" in source
    assert "tracker.dataset.analyticsLoadState = 'loading'" in source


def test_generic_analytics_load_tracker_copied_shell_debt_is_burned_down() -> None:
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    relative = TARGET_PATH.relative_to(ROOT).as_posix()

    assert relative not in payload["files"]
