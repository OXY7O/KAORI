from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OVERVIEW = ROOT / 'app' / 'templates' / 'reports' / 'overview'
SERVICE = ROOT / 'app' / 'reports' / 'overview' / 'service.py'
PRESENTATION = ROOT / 'app' / 'reports' / 'overview' / 'presentation.py'


def read(path: Path) -> str:
    return path.read_text()


def test_reports_overview_is_full_width_without_right_sidebar() -> None:
    source = read(OVERVIEW / 'index.html')

    assert 'data-reports-overview-layout="operational-full-width"' in source
    assert 'Operational Reporting' in source
    assert 'Generate Report' in source
    assert 'View Generated Reports' in source
    assert 'page_hero.aside_classes()' not in source
    assert 'Reports overview actions' not in source
    assert 'xl:grid-cols-[minmax(0,1fr)_390px]' not in source
    assert '<aside' not in source

    assert '_reporting_operations.html' in source
    assert '_recent_reports.html' in source
    assert '_reporting_coverage.html' in source

    for legacy_partial in (
        '_reporting_context.html',
        '_summary_cards.html',
        '_coverage_pipeline_workspace.html',
        '_data_collection_status.html',
        '_current_status.html',
        '_reporting_operating_model.html',
        '_related_information.html',
    ):
        assert legacy_partial not in source


def test_reporting_posture_is_embedded_in_the_hero() -> None:
    source = read(OVERVIEW / 'index.html')
    service = read(SERVICE)
    presentation = read(PRESENTATION)

    assert 'aria-label="Reporting posture"' in source
    assert 'data-reports-hero-layout="compact-posture"' in source
    assert 'payload.summary_cards' in source
    assert 'kaori-hero-tile rounded-xl border px-4 py-3' not in source
    assert 'border-t border-white/20' in source
    assert 'sm:divide-x sm:divide-white/20' in source
    assert 'min-h-[13rem]' not in source
    assert 'lg:min-h-[14.5rem]' not in source
    for label in ('Generated', 'Ready', 'In Progress', 'Failed'):
        assert f"'label': '{label}'" in service
        assert f"'label': '{label}'" in presentation

    assert "'page_title': 'Reports'" in service
    assert 'Generate, schedule, retain, and audit governed reporting artifacts.' in service


def test_reporting_operations_are_one_compact_operational_workspace() -> None:
    source = read(OVERVIEW / 'partials' / '_reporting_operations.html')
    service = read(SERVICE)

    assert 'Reporting Operations' in source
    assert 'payload.reporting_operations' in source
    assert 'lg:grid-cols-3' in source
    assert '{% import "components/table_label.html" as table_label %}' in source
    assert 'table_label.status_indicator_label' in source

    for label in ('Generation Queue', 'Active Schedules', 'Artifact Storage'):
        assert label in service

    assert "url_for('reports.generate_report')" in service
    assert "url_for('reports.schedules')" in service
    assert "url_for('reports.storage')" in service


def test_recent_reports_use_canonical_artifact_registry_columns() -> None:
    source = read(OVERVIEW / 'partials' / '_recent_reports.html')
    service = read(SERVICE)

    assert 'components/table.html' in source
    assert 'components/table_label.html' in source
    for label in ('Report', 'Cluster', 'Format', 'Status', 'Generated', 'Size', 'Action'):
        assert f'>{label}<' in source

    assert 'report.cluster_name' in source
    assert 'report.output_format' in source
    assert 'report.file_size' in source
    assert 'status_indicator_label' in source
    assert "'cluster_name':" in service
    assert "'output_format':" in service
    assert 'select(Cluster).where(Cluster.id.in_(cluster_ids))' in service

    assert 'Scope</th>' not in source
    assert 'Type</th>' not in source
    assert 'Created</th>' not in source


def test_reporting_coverage_is_one_full_width_family_workspace() -> None:
    source = read(OVERVIEW / 'partials' / '_reporting_coverage.html')
    service = read(SERVICE)

    assert 'Reporting Coverage' in source
    assert 'payload.reporting_coverage' in source
    assert 'lg:grid-cols-2' in source
    assert 'data-report-family="{{ group.key }}"' in source
    assert 'Governed scope.' in source
    assert 'analytics uses PDF/CSV while inventory uses XLSX/CSV.' in source

    for label in ('Analytics Reports', 'Inventory Reports'):
        assert label in service
    for format_label in ("'PDF'", "'CSV'", "'XLSX'"):
        assert format_label in service

    assert 'REPORT_FAMILY_ANALYTICS' in service
    assert 'REPORT_FAMILY_INVENTORY' in service
    assert 'for spec in REPORT_TYPE_SPECS' in service


def test_overview_does_not_expose_storage_or_schedule_configuration_details() -> None:
    combined = '\n'.join(
        read(path)
        for path in (
            OVERVIEW / 'index.html',
            OVERVIEW / 'partials' / '_reporting_operations.html',
            OVERVIEW / 'partials' / '_recent_reports.html',
            OVERVIEW / 'partials' / '_reporting_coverage.html',
        )
    )

    for forbidden in (
        'Access Key',
        'Secret Key',
        'Bucket Prefix',
        'Retention Days',
        'Cron Expression',
        'Storage Path',
    ):
        assert forbidden not in combined


def test_overview_partials_import_table_label_when_used():
    partials = [
        Path('app/templates/reports/overview/partials/_reporting_operations.html'),
        Path('app/templates/reports/overview/partials/_recent_reports.html'),
        Path('app/templates/reports/overview/partials/_reporting_coverage.html'),
    ]
    import_line = '{% import "components/table_label.html" as table_label %}'
    for path in partials:
        source = path.read_text()
        if 'table_label.' in source:
            assert import_line in source, f'{path} uses table_label without importing it'
