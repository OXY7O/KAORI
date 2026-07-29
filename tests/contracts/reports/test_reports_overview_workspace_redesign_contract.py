from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OVERVIEW = ROOT / 'app' / 'templates' / 'reports' / 'overview'
SERVICE = ROOT / 'app' / 'reports' / 'overview' / 'service.py'


def read(path: Path) -> str:
    return path.read_text()


def test_reports_overview_uses_short_hero_and_standard_context_panel() -> None:
    source = read(OVERVIEW / 'index.html')
    service = read(SERVICE)

    assert 'Generate governed infrastructure reports from connected KAORI data sources.' in service
    assert 'Infrastructure reporting center' not in source
    assert 'Infrastructure Reporting Center' in source
    assert 'Reporting Readiness' in source
    assert 'page_hero.context_status_badge' in source
    assert "'Available Types'" in source
    assert "'Active Schedules'" in source
    assert 'Templates' in source
    assert 'Generate' in source


def test_reporting_overview_is_general_and_integration_driven() -> None:
    source = read(OVERVIEW / 'partials' / '_reporting_context.html')
    service = read(SERVICE)

    assert 'Integration-Driven Reporting Workspace' in source
    assert 'Integration-Driven Coverage' in service
    assert 'Reusable Report Contracts' in service
    assert 'Governed Artifact Lifecycle' in service
    assert 'Automation & Delivery' in service
    assert 'any supported infrastructure domain' in service
    assert 'dashboard screenshots' not in source


def test_coverage_and_pipeline_use_short_tabs_and_scalable_expandables() -> None:
    workspace = read(OVERVIEW / 'partials' / '_coverage_pipeline_workspace.html')
    coverage = read(OVERVIEW / 'partials' / '_report_type_coverage.html')
    pipeline = read(OVERVIEW / 'partials' / '_pipeline_status.html')

    assert "reportWorkspaceTab: 'coverage'" in read(OVERVIEW / 'index.html')
    assert "activateReportWorkspaceTab('coverage')" in workspace
    assert "activateReportWorkspaceTab('pipeline')" in workspace
    assert 'Reporting Capability' in workspace
    assert '\n                    Types\n' in workspace
    assert '\n                    Pipeline\n' in workspace
    assert 'Report Type Coverage' not in workspace
    assert 'Reporting Pipeline Status' not in workspace

    assert 'openCoverageDomain: null' in coverage
    assert 'openCoverageDomain ===' in coverage
    assert 'x-collapse' in coverage
    assert 'payload.report_type_coverage.domains' in coverage
    assert 'md:grid-cols-2 2xl:grid-cols-3' in coverage
    assert 'overflow-x-auto' not in coverage

    assert 'openPipelineStage: null' in pipeline
    assert 'openPipelineStage ===' in pipeline
    assert 'x-collapse' in pipeline
    assert 'aria-label="Generate report pipeline stages"' in pipeline
    assert 'space-y-2' in pipeline
    assert 'overflow-x-auto' not in pipeline
    assert 'min-h-[720px]' not in coverage


def test_current_status_and_operating_model_are_closed_by_default() -> None:
    current_status = read(OVERVIEW / 'partials' / '_current_status.html')
    operating_model = read(OVERVIEW / 'partials' / '_reporting_operating_model.html')

    assert 'x-data="{ open: false }"' in current_status
    assert 'x-data="{ open: false }"' in operating_model
    assert 'x-show="open" x-collapse x-cloak' in current_status
    assert 'x-show="open" x-collapse x-cloak' in operating_model
    assert 'Ready ·' in current_status
    assert 'Reporting Operating Model' in operating_model


def test_infrastructure_collection_covers_ready_available_planned_and_reserved_integrations() -> None:
    source = read(SERVICE)
    template = read(OVERVIEW / 'partials' / '_data_collection_status.html')

    for label in (
        'Kubernetes API',
        'Prometheus / Thanos',
        'Alertmanager',
        'Local Filesystem',
        'MinIO / S3-Compatible Storage',
        'Server & VM Inventory',
        'HCI Provider APIs',
        'Vault & Secret Providers',
        'Telegram',
        'Email, Slack & Webhook',
    ):
        assert label in source

    for stage in ('Ready Now', 'Available to Configure', 'Planned', 'Reserved'):
        assert stage in template

    assert 'Review Integrations' in template


def test_related_kaori_information_is_available_in_right_column() -> None:
    index = read(OVERVIEW / 'index.html')
    related = read(OVERVIEW / 'partials' / '_related_information.html')
    service = read(SERVICE)

    assert '_related_information.html' in index
    assert 'Related KAORI Information' in related
    for label in (
        'Generate Report',
        'Report Templates',
        'Report Schedules',
        'Report Storage',
        'Infrastructure Integrations',
    ):
        assert label in service


def test_report_overview_headings_use_title_case_where_appropriate() -> None:
    combined = '\n'.join(
        read(path)
        for path in [
            OVERVIEW / 'index.html',
            *sorted((OVERVIEW / 'partials').glob('*.html')),
        ]
    )

    required = (
        'Infrastructure Reporting Center',
        'Reporting Activity Snapshot',
        'Recent Generated Reports',
        'Reporting Capability',
        'Infrastructure Data Collection',
        'Current Status',
        'Reporting Operating Model',
        'Related KAORI Information',
    )
    for label in required:
        assert label in combined

    assert 'Report engine' not in combined
    assert 'Infrastructure reporting center' not in combined
    assert 'Create first report' not in combined
