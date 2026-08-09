from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OVERVIEW = ROOT / 'app' / 'templates' / 'reports' / 'overview'
SERVICE = ROOT / 'app' / 'reports' / 'overview' / 'service.py'
PRESENTATION = ROOT / 'app' / 'reports' / 'overview' / 'presentation.py'


def read(path: Path) -> str:
    return path.read_text()


def test_reports_overview_hero_uses_canonical_kaori_shared_geometry() -> None:
    source = read(OVERVIEW / 'index.html')

    assert 'data-reports-overview-layout="operational-full-width"' in source
    assert 'Operational Reporting' in source
    assert 'page_hero.shell_classes()' in source
    assert 'page_hero.layout_classes()' in source
    assert 'page_hero.content_classes()' in source
    assert 'page_hero.intro(' in source
    assert 'page_hero.title_classes()' in source
    assert 'page_hero.description_classes()' in source
    assert 'page_hero.metadata_row_classes()' in source
    assert 'page_hero.context_card(' in source
    assert 'data-reports-hero-layout="canonical-7-5"' in source

    # Hero geometry and actions are owned by the shared component, not this page.
    assert 'min-h-[13rem]' not in source
    assert 'lg:min-h-[14.5rem]' not in source
    assert 'xl:grid-cols-12' not in source
    assert 'xl:col-span-' not in source
    assert 'page_hero.primary_action_classes()' not in source
    assert 'kaori-hero-chip' not in source
    assert 'data-reporting-posture-strip' not in source

    assert '_reporting_operations.html' in source
    assert '_recent_reports.html' in source
    assert '_reporting_coverage.html' in source


def test_reports_overview_hero_respects_context_density_and_metadata_contract() -> None:
    source = read(OVERVIEW / 'index.html')
    service = read(SERVICE)
    presentation = read(PRESENTATION)

    # Metadata communicates scope/identity, while health stays in semantic context status.
    assert "payload.selected_cluster_label" in source
    assert "'S3 Artifact Storage'" in source
    assert "'Governed Artifact Lifecycle'" in source
    assert "page_hero.meta_label('triangle-alert', 'Reporting Degraded')" not in source

    # Canonical context card: one status, exactly two compact metrics, one action.
    assert "'Reporting Posture'" in source
    assert "'Artifact Readiness'" in source
    assert "('circle-check', 'Ready', ready_card.value, 'Available artifacts')" in source
    assert "hero_secondary_label" in source
    assert "hero_action_label" in source
    assert "hero_action_url" in source
    assert "View Generated Reports" not in source
    assert "Verify Storage" not in source

    # Degraded storage changes posture/action without changing hero geometry.
    assert "hero_status_label = 'Degraded'" in source
    assert "hero_status_tone = 'warning'" in source
    assert "hero_action_label = 'Open Storage'" in source

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
