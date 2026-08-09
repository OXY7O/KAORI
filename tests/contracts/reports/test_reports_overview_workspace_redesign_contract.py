from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OVERVIEW = ROOT / 'app' / 'templates' / 'reports' / 'overview'
SERVICE = ROOT / 'app' / 'reports' / 'overview' / 'service.py'
PRESENTATION = ROOT / 'app' / 'reports' / 'overview' / 'presentation.py'


def read(path: Path) -> str:
    return path.read_text()


def test_reports_overview_uses_canonical_hero_and_statistics_first_layout() -> None:
    source = read(OVERVIEW / 'index.html')

    assert 'data-reports-overview-layout="operational-full-width"' in source
    assert 'Operational Reporting' in source
    assert 'page_hero.shell_classes()' in source
    assert 'page_hero.layout_classes()' in source
    assert 'page_hero.content_classes()' in source
    assert 'page_hero.context_card(' in source
    assert 'data-reports-hero-layout="canonical-7-5"' in source

    assert '_reporting_operations.html' in source
    assert '_reporting_statistics.html' in source
    assert '_reporting_portfolio.html' in source
    assert '_reporting_coverage.html' in source
    assert '_recent_reports.html' not in source

    # Overview is posture/statistics-first; artifact browsing stays on Generated Reports.
    assert 'Recent Generated Reports' not in source
    assert 'min-h-[13rem]' not in source
    assert 'xl:grid-cols-12' not in source


def test_reports_overview_hero_keeps_health_in_canonical_context_card() -> None:
    source = read(OVERVIEW / 'index.html')
    service = read(SERVICE)

    assert 'payload.selected_cluster_label' in source
    assert "'S3 Artifact Storage'" in source
    assert "'Governed Artifact Lifecycle'" in source
    assert "'Reporting Posture'" in source
    assert "'Artifact Readiness'" in source
    assert "('circle-check', 'Ready', ready_card.value, 'Available artifacts')" in source
    assert "hero_action_label = 'Open Storage'" in source
    assert "hero_status_label = 'Degraded'" in source

    for label in ('Generated', 'Ready', 'In Progress', 'Failed'):
        assert f"'label': '{label}'" in service


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


def test_reporting_statistics_replace_recent_artifact_table() -> None:
    source = read(OVERVIEW / 'partials' / '_reporting_statistics.html')
    service = read(SERVICE)
    presentation = read(PRESENTATION)

    assert 'Reporting Statistics' in source
    assert 'payload.artifact_statistics' in source
    assert 'Open Generated Reports' in source
    for label in ('Requests This Month', 'Completion Rate', 'Artifact Footprint', 'Custom Templates'):
        assert label in service
        assert label in presentation

    assert 'get_artifact_statistics(report_counts)' in service
    assert 'func.sum(Report.file_size_bytes)' in service
    assert 'get_recent_reports(' not in service
    assert 'serialize_recent_report(' not in service


def test_reporting_portfolio_surfaces_family_format_and_automation_mix() -> None:
    source = read(OVERVIEW / 'partials' / '_reporting_portfolio.html')
    service = read(SERVICE)

    assert 'Reporting Portfolio' in source
    assert 'Artifact Families' in source
    assert 'Output Formats' in source
    assert 'Automation & Reuse' in source
    assert 'payload.artifact_portfolio.families' in source
    assert 'payload.artifact_portfolio.formats' in source
    assert 'payload.automation_summary.active_schedules' in source

    assert 'def get_artifact_portfolio()' in service
    assert '.group_by(Report.report_type)' in service
    assert '.group_by(Report.output_format)' in service
    assert 'def get_automation_summary(' in service


def test_reporting_capability_is_compact_not_a_second_catalog() -> None:
    source = read(OVERVIEW / 'partials' / '_reporting_coverage.html')
    service = read(SERVICE)

    assert 'Reporting Capability' in source
    assert 'payload.reporting_coverage' in source
    assert 'group.contract_count' in source
    assert 'Formats' in source
    assert 'group[\'items\']' not in source
    assert 'for item in group' not in source

    for label in ('Analytics Reports', 'Inventory Reports'):
        assert label in service
    assert "group['contract_count'] = len(group['items'])" in service


def test_overview_does_not_expose_configuration_or_artifact_registry_details() -> None:
    combined = '\n'.join(
        read(path)
        for path in (
            OVERVIEW / 'index.html',
            OVERVIEW / 'partials' / '_reporting_operations.html',
            OVERVIEW / 'partials' / '_reporting_statistics.html',
            OVERVIEW / 'partials' / '_reporting_portfolio.html',
            OVERVIEW / 'partials' / '_reporting_coverage.html',
        )
    )

    for forbidden in (
        'Access Key', 'Secret Key', 'Bucket Prefix', 'Retention Days',
        'Cron Expression', 'Storage Path', 'Recent Generated Reports',
    ):
        assert forbidden not in combined
