from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OVERVIEW = ROOT / 'app' / 'templates' / 'reports' / 'overview'
SERVICE = ROOT / 'app' / 'reports' / 'overview' / 'service.py'
PRESENTATION = ROOT / 'app' / 'reports' / 'overview' / 'presentation.py'


def read(path: Path) -> str:
    return path.read_text()


def test_reports_overview_uses_canonical_hero_and_separate_governed_sections() -> None:
    source = read(OVERVIEW / 'index.html')

    assert 'data-reports-overview-layout="operational-full-width"' in source
    assert "page_hero.intro('file-text', 'Reports', 'file-text')" in source
    assert '<h1 class="{{ page_hero.title_classes() }}">Overview</h1>' in source
    assert 'Reports Overview' in source
    assert 'page_hero.shell_classes()' in source
    assert 'page_hero.layout_classes()' in source
    assert 'page_hero.content_classes()' in source
    assert 'page_hero.context_card(' in source
    assert 'data-reports-hero-layout="canonical-7-5"' in source

    assert '_reporting_operational_posture.html' in source
    assert '_reporting_estate_capability.html' in source
    assert '_reporting_contracts_automation.html' in source
    assert '{% import "components/section_intro.html" as section_intro %}' in source
    assert "section_intro.render('Reporting Landscape'," in source
    assert "section_intro.render('Reporting Governance'," in source
    assert 'aria-labelledby="reporting-landscape-heading"' in source
    assert 'aria-labelledby="reporting-governance-heading"' in source
    for legacy in (
        '_reporting_operations.html',
        '_reporting_statistics.html',
        '_reporting_portfolio.html',
        '_reporting_coverage.html',
        '_recent_reports.html',
    ):
        assert legacy not in source

    assert 'min-h-[13rem]' not in source
    assert 'xl:grid-cols-12' not in source


def test_reports_overview_hero_keeps_health_in_canonical_context_card() -> None:
    source = read(OVERVIEW / 'index.html')
    service = read(SERVICE)

    assert 'payload.selected_cluster_label' in source
    assert "'S3 Artifact Storage'" in source
    assert "' Reporting Domains'" in source
    assert 'payload.report_type_coverage.domain_count' in source
    assert "'Reporting Posture'" in source
    assert "'Artifact Readiness'" in source
    assert "('circle-check', 'Ready', ready_card.value, 'Available artifacts')" in source
    assert re.search(r"hero_action_label = ['\"]Open Storage['\"]", source)
    assert 'hero_status_label = payload.reporting_posture.label' in source
    assert "return {'label': 'Degraded', 'tone': 'warning', 'reason': 'storage'}" in service
    assert "return {'label': 'Degraded', 'tone': 'warning', 'reason': 'queue'}" in service

    for label in ('Generated', 'Ready', 'In Progress', 'Failed'):
        assert f"'label': '{label}'" in service


def test_operational_posture_merges_runtime_and_generation_statistics() -> None:
    source = read(OVERVIEW / 'partials' / '_reporting_operational_posture.html')
    service = read(SERVICE)
    presentation = read(PRESENTATION)

    assert '{% import "components/table_label.html" as table_label %}' in source
    assert 'data-reports-overview-block="operational-posture"' in source
    assert 'Reporting Operational Posture' in source
    assert 'Runtime Health' in source
    assert 'Generation Performance' in source
    assert 'payload.reporting_operations' in source
    assert 'payload.artifact_statistics[:2]' in source
    assert 'data-reporting-performance-reading="true"' in source
    assert 'Operational Reading' in source
    assert 'Completion Rate measures resolved requests only' in source
    assert 'table_label.status_indicator_label' in source

    for label in ('Generation Queue', 'Active Schedules', 'Artifact Storage'):
        assert label in service
    for label in ('Requests This Month', 'Completion Rate'):
        assert label in service
        assert label in presentation

    assert 'data-report-storage-incident="overview"' in source
    assert 'S3 Artifact Storage Disconnected' in source
    assert 'Verify Now' in source


def test_estate_and_contracts_are_distinct_source_owned_cards() -> None:
    source = read(OVERVIEW / 'partials' / '_reporting_estate_capability.html')
    contracts = read(OVERVIEW / 'partials' / '_reporting_contracts_automation.html')
    service = read(SERVICE)
    presentation = read(PRESENTATION)

    assert 'data-reports-overview-block="contracts-automation"' in contracts
    assert 'aria-labelledby="contracts-automation-title"' in contracts
    assert 'data-reports-overview-block="estate-capability"' in source
    assert 'Report Coverage &amp; Artifact Estate' in source
    assert 'Reporting Domain Coverage' in source
    assert 'Artifact Estate' in source
    assert 'Contracts &amp; Automation' in contracts
    assert 'payload.report_type_coverage.domains' in source
    assert 'data-report-domain-coverage="true"' in source
    assert 'Publication Boundary' in source
    assert 'Published = registered contract + renderer; candidates cannot run.' in source
    assert 'payload.summary_cards[0]' in source
    assert 'payload.artifact_statistics[2]' in source
    assert 'data-artifact-estate-snapshot="true"' in source
    assert 'Retained Artifacts' in source
    assert 'data-artifact-estate-distribution="true"' in source
    assert 'payload.artifact_portfolio.families' in source
    assert 'Retained Artifact Mix' in source
    assert 'data-artifact-family-tip' not in source
    assert 'payload.artifact_portfolio.formats' in source
    assert 'data-output-contract="true"' in source
    assert 'Output Contract' in source
    assert 'Analytics Reports' in source
    assert 'PDF · XLSX · CSV' in source
    assert 'Inventory Reports' in source
    assert 'XLSX · CSV' in source
    assert 'Candidate Domains' in source
    assert 'Contract + renderer required' in source
    assert 'Contracts &amp; Automation' in contracts
    assert 'payload.automation_summary.active_schedules' in contracts
    assert 'payload.reporting_coverage' in contracts
    assert 'data-contract-family-summary="true"' in contracts
    assert 'Published Contract Families' in contracts
    assert 'data-contract-automation-boundary="true"' in contracts
    assert 'Automation Boundary' in contracts
    assert 'group.contract_count' in contracts
    assert 'Generated Reports' in source
    assert 'Templates' in source
    assert "url_for('reports.report_templates')" in source
    assert "url_for('reports.templates')" not in source
    assert 'text-[' not in source

    for label in ('Artifact Footprint', 'Custom Templates'):
        assert label in service
        assert label in presentation
    assert 'def get_artifact_portfolio()' in service
    assert 'def get_automation_summary(' in service
    assert "group['contract_count'] = len(group['items'])" in service


def test_estate_visual_density_reuses_evidence_tiles_and_preserves_readability() -> None:
    source = read(OVERVIEW / 'partials' / '_reporting_estate_capability.html')

    assert '{% import "components/operational_evidence_tile.html" as evidence_tile %}' in source
    assert 'sm:line-clamp-2 sm:min-h-10' in source
    assert 'title="{{ domain.description }}"' in source
    assert 'xl:whitespace-nowrap' in source
    assert 'Published = registered contract + renderer; candidates cannot run.' in source
    assert 'data-artifact-family-tiles="true"' in source
    assert 'data-artifact-format-tiles="true"' in source
    assert "evidence_tile.snapshot(item.label, item.value, item.icon, 'Retained family')" in source
    assert "evidence_tile.snapshot(item.label, item.value, 'file-stack', 'Output format')" in source
    assert 'mt-auto pt-4' not in source
    assert 'Ready or archived artifacts.' in source
    assert 'Ready or archived artifacts retained in the reporting estate.' not in source
    assert 'Contracts &amp; Automation' not in source
    catalog = read(ROOT / 'app/definitions/catalogs/reports/coverage.yaml')
    assert (
        'Planned only. No Vault Secret export or report execution without approved scope, committed data, and safety.'
        in catalog
    )


def test_overview_removes_floating_heading_icons_without_losing_operational_icons() -> None:
    estate = read(OVERVIEW / 'partials' / '_reporting_estate_capability.html')
    contracts = read(OVERVIEW / 'partials' / '_reporting_contracts_automation.html')

    # Trailing icons in section headers are decorative and disconnect from the text.
    for icon in ('network', 'archive', 'layers-2', 'file-stack'):
        assert f'<i data-lucide="{icon}"' not in estate
    assert '<i data-lucide="folder-tree"' not in contracts

    # Preserve icons that communicate report-domain identity or metric meaning.
    assert 'data-lucide="{{ domain.icon }}"' in estate
    assert "evidence_tile.snapshot(item.label, item.value, item.icon, 'Retained family')" in estate
    assert 'data-lucide="{{ group.icon }}"' in contracts


def test_overview_is_not_an_artifact_registry_or_configuration_page() -> None:
    combined = '\n'.join(
        read(path)
        for path in (
            OVERVIEW / 'index.html',
            OVERVIEW / 'partials' / '_reporting_operational_posture.html',
            OVERVIEW / 'partials' / '_reporting_estate_capability.html',
            OVERVIEW / 'partials' / '_reporting_contracts_automation.html',
        )
    )

    for forbidden in (
        'Access Key',
        'Secret Key',
        'Bucket Prefix',
        'Retention Days',
        'Cron Expression',
        'Storage Path',
        'Recent Generated Reports',
        'Reporting Statistics',
        'Reporting Portfolio',
        'Reporting Capability',
    ):
        assert forbidden not in combined
