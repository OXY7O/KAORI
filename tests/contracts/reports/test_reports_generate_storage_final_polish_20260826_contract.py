from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GENERATE_TEMPLATE = ROOT / 'app/templates/reports/generate/index.html'
TEMPLATES_TEMPLATE = ROOT / 'app/templates/reports/report_templates/index.html'
TEMPLATES_SERVICE = ROOT / 'app/reports/report_templates/service.py'
STORAGE_TEMPLATE = ROOT / 'app/templates/reports/storage/index.html'
STORAGE_SERVICE = ROOT / 'app/reports/storage/service.py'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def hero_metadata_count(source: str) -> int:
    marker = '<div class="{{ page_hero.metadata_row_classes() }}">'
    block = source.split(marker, 1)[1].split('</div>', 1)[0]
    return block.count('page_hero.meta_label(')


def test_artifact_contract_uses_full_width_contract_and_format_guidance() -> None:
    source = read(GENERATE_TEMPLATE)
    artifact = source.split('id="generate-wizard-step-3"', 1)[1].split(
        'id="generate-wizard-step-4"', 1
    )[0]

    assert 'data-artifact-contract-layout="full-width"' in artifact
    assert 'data-artifact-format-guide="true"' in artifact
    assert '>PDF</span> for governed publication' in artifact
    assert '>XLSX</span> for drill-down and evidence review' in artifact
    assert '>CSV</span> for portable tabular evidence' in artifact
    assert 'Publication Readiness' in artifact
    assert 'lg:grid-cols-3' not in artifact


def test_report_content_is_full_width_and_contract_moves_below_section_grid() -> None:
    source = read(GENERATE_TEMPLATE)
    content = source.split('id="generate-wizard-step-4"', 1)[1].split(
        'id="generate-wizard-step-5"', 1
    )[0]

    assert 'data-report-content-layout="full-width"' in content
    assert 'data-content-contract="full-width"' in content
    assert 'aria-label="Report content guidance"' not in content
    assert 'lg:grid-cols-3' not in content
    assert content.index('id="selected-section-list"') < content.index('data-content-contract="full-width"')
    assert 'Only sections published for the selected report type can be submitted. KAORI validates the selection again before queueing.' in content


def test_report_templates_and_storage_heroes_cap_metadata_at_three() -> None:
    templates = read(TEMPLATES_TEMPLATE)
    storage = read(STORAGE_TEMPLATE)

    assert hero_metadata_count(templates) == 3
    assert hero_metadata_count(storage) == 3


def test_requested_report_copy_is_shortened_without_losing_contract_meaning() -> None:
    templates_service = read(TEMPLATES_SERVICE)
    storage_service = read(STORAGE_SERVICE)
    storage_template = read(STORAGE_TEMPLATE)

    assert (
        'Manage protected system templates and reusable custom report structures for Analytics PDF/XLSX/CSV and Inventory XLSX/CSV.'
        in templates_service
    )
    assert (
        'Review report storage readiness, integrity, and lifecycle ownership for PDF/XLSX/CSV artifacts.'
        in storage_service
    )
    assert (
        'S3-compatible target for generated reports and verification evidence.'
        in storage_template
    )

    assert 'while preserving canonical sections and reusable generation defaults.' not in templates_service
    assert 'including backend and reference integrity, verification results, retained coverage' not in storage_service
    assert 'lifecycle-managed storage records' not in storage_template


def test_reports_storage_uses_contract_first_three_workspace_redesign() -> None:
    source = read(STORAGE_TEMPLATE)

    assert 'data-storage-workspace-shell="true"' in source
    assert 'data-storage-overview-layout="dense-posture-grid"' in source
    assert 'data-storage-integrity-layout="posture-actions-results"' in source
    assert 'data-storage-retention-layout="lifecycle-governance"' in source
    assert 'data-storage-posture-layout="editorial-readiness"' not in source

    assert 'Storage Posture' in source
    assert 'Artifact Coverage' in source
    assert 'Access &amp; Readiness' in source
    assert 'Integrity Posture' in source
    assert 'Generated Report Lifecycle Policy' in source
    assert 'Ownership Boundary' in source

    # Worker-owned verification remains the execution model after the redesign.
    assert "{% include 'reports/storage/_verification_status.html' %}" in source
    verification_partial = read(ROOT / 'app/templates/reports/storage/_verification_status.html')
    assert 'Worker-owned write → confirm → delete test.' in verification_partial
