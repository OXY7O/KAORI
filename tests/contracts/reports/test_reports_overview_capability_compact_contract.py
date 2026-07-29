from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OVERVIEW = ROOT / 'app' / 'templates' / 'reports' / 'overview' / 'partials'


def read(name: str) -> str:
    return (OVERVIEW / name).read_text()


def test_reporting_capability_tabs_are_short_and_accessible() -> None:
    source = read('_coverage_pipeline_workspace.html')

    assert 'Reporting Capability' in source
    assert 'aria-label="Reporting capability tabs"' in source
    assert '\n                    Types\n' in source
    assert '\n                    Pipeline\n' in source
    assert 'Report Type Coverage' not in source
    assert 'Reporting Pipeline Status' not in source


def test_report_coverage_expands_by_domain_instead_of_rendering_long_lanes() -> None:
    source = read('_report_type_coverage.html')

    assert 'x-data="{ openCoverageDomain: null }"' in source
    assert '@click="openCoverageDomain = openCoverageDomain ===' in source
    assert ':aria-expanded="openCoverageDomain ===' in source
    assert 'x-collapse' in source
    assert 'line-clamp-2' in source
    assert 'overflow-x-auto' not in source
    assert 'w-64 shrink-0' not in source


def test_pipeline_uses_compact_expandable_stage_rows() -> None:
    source = read('_pipeline_status.html')

    assert 'x-data="{ openPipelineStage: null }"' in source
    assert '@click="openPipelineStage = openPipelineStage ===' in source
    assert ':aria-expanded="openPipelineStage ===' in source
    assert 'x-collapse' in source
    assert 'aria-label="Generate report pipeline stages"' in source
    assert 'space-y-2' in source
    assert 'overflow-x-auto' not in source
    assert 'w-64 shrink-0' not in source
