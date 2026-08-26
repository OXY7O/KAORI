from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def hero_metadata_count(source: str) -> int:
    marker = '<div class="{{ page_hero.metadata_row_classes() }}">'
    block = source.split(marker, 1)[1].split('</div>', 1)[0]
    return block.count('page_hero.meta_label(')


def test_storage_overview_uses_posture_target_access_coverage_governance_hierarchy() -> None:
    source = read('app/templates/reports/storage/index.html')
    overview = source.split("{% if payload.workspace == 'overview' %}", 1)[1].split(
        "{% elif payload.workspace == 'integrity' %}", 1
    )[0]

    assert 'data-storage-overview-layout="dense-posture-grid"' in overview
    for heading in (
        'Storage Posture',
        'Storage Target',
        'Access &amp; Readiness',
        'Artifact Coverage',
        'Governance Boundary',
        'Object Key Contract',
    ):
        assert heading in overview

    assert 'data-storage-object-key-contract="readable"' in overview
    object_key = overview.split('data-storage-object-key-contract="readable"', 1)[1].split('</div>', 2)[0]
    assert 'overflow-x-auto' not in object_key
    assert 'whitespace-nowrap' not in object_key
    assert 'data-kaori-copy' in object_key


def test_storage_integrity_uses_posture_actions_latest_verification_and_reference_result() -> None:
    source = read('app/templates/reports/storage/index.html')
    integrity = source.split("{% elif payload.workspace == 'integrity' %}", 1)[1].split(
        "{% elif payload.workspace == 'retention' %}", 1
    )[0]

    assert 'data-storage-integrity-layout="posture-actions-results"' in integrity
    for heading in (
        'Integrity Posture',
        'Verification Actions',
        'Latest Verification',
        'Reference Integrity',
        'Artifact Integrity Scan',
    ):
        assert heading in integrity

    assert 'data-storage-integrity-guidance="true"' not in integrity
    assert 'Verification and integrity have different scopes.' not in integrity
    assert 'data-storage-integrity-actions="action-cards"' in integrity
    assert "{% include 'reports/storage/_verification_status.html' %}" in integrity
    verification_partial = read('app/templates/reports/storage/_verification_status.html')
    assert 'Strong Backend Verification' in verification_partial


def test_reports_requested_copy_is_compact() -> None:
    generate_service = read('app/reports/generate/service.py')
    storage_service = read('app/reports/storage/service.py')
    templates_service = read('app/reports/report_templates/service.py')

    assert (
        'Build governed reports from connected data and approved formats. Analytics: PDF/XLSX/CSV · Inventory: XLSX/CSV.'
        in generate_service
    )
    assert (
        'Review report storage readiness, integrity, and lifecycle ownership for PDF/XLSX/CSV artifacts.'
        in storage_service
    )
    assert (
        'Manage protected system templates and reusable custom report structures for Analytics PDF/XLSX/CSV and Inventory XLSX/CSV.'
        in templates_service
    )


def test_reports_section_headings_use_canonical_icons() -> None:
    overview = read('app/templates/reports/overview/partials/_reporting_estate_capability.html')
    schedules = read('app/templates/reports/schedules/index.html')

    contracts = overview.split('id="contracts-automation-title"', 1)[0][-1200:]
    assert 'data-lucide="workflow"' in contracts
    assert 'table_ui.block_icon_classes()' in contracts
    assert 'data-lucide="workflow" class="h-5 w-5"' in contracts
    assert 'flex min-w-0 items-start gap-3' in contracts

    registry = schedules.split('aria-label="Schedule Registry"', 1)[1].split('schedule-registry-loading', 1)[0]
    assert 'data-lucide="calendar-clock"' in registry
    assert 'table_ui.block_icon_classes()' in registry
    assert 'data-lucide="calendar-clock" class="h-5 w-5"' in registry
    assert 'flex min-w-0 items-start gap-3' in registry

    runs = schedules.split('aria-label="Recent Schedule Runs"', 1)[1].split('schedule-runs-loading', 1)[0]
    assert 'data-lucide="history"' in runs
    assert 'table_ui.block_icon_classes()' in runs
    assert 'data-lucide="history" class="h-5 w-5"' in runs
    assert 'flex min-w-0 items-start gap-3' in runs


def test_report_templates_and_storage_heroes_remain_max_three_metadata() -> None:
    templates = read('app/templates/reports/report_templates/index.html')
    storage = read('app/templates/reports/storage/index.html')
    assert hero_metadata_count(templates) <= 3
    assert hero_metadata_count(storage) <= 3


def test_schedule_registry_and_runs_use_canonical_filter_surface() -> None:
    schedules = read('app/templates/reports/schedules/index.html')

    registry = schedules.split('aria-label="Schedule Registry"', 1)[1].split('<div class="overflow-x-auto">', 1)[0]
    runs = schedules.split('aria-label="Recent Schedule Runs"', 1)[1].split('<div class="overflow-x-auto">', 1)[0]

    for block in (registry, runs):
        assert 'table_ui.inventory_filter_bar_classes()' in block
        assert 'registry_ui.filter_form' in block
        assert "payload.pagination.per_page, 'mt-4'" not in block
        assert "payload.run_pagination.per_page, 'mt-4'" not in block

    registry_header = registry.split('</header>', 1)[0]
    runs_header = runs.split('</header>', 1)[0]
    assert 'registry_ui.filter_form' not in registry_header
    assert 'registry_ui.filter_form' not in runs_header


def test_storage_overview_uses_dense_two_by_two_information_grid_without_duplicate_summary_metrics() -> None:
    source = read('app/templates/reports/storage/index.html')
    overview = source.split("{% if payload.workspace == 'overview' %}", 1)[1].split(
        "{% elif payload.workspace == 'integrity' %}", 1
    )[0]

    assert 'data-storage-overview-layout="dense-posture-grid"' in overview
    assert 'data-storage-overview-main-grid="target-readiness"' in overview
    assert 'data-storage-overview-bottom-grid="coverage-governance"' in overview
    assert 'data-storage-posture-summary="compact-cards"' in overview
    assert 'data-storage-artifact-evidence="coverage-contract"' in overview
    assert 'data-storage-governance-contract="compact"' in overview

    # The top strip owns the numeric posture metrics; coverage below explains provenance,
    # so Ready Reports / Tracked Size must not be repeated inside Artifact Coverage.
    coverage = overview.split('data-storage-artifact-evidence="coverage-contract"', 1)[1].split('</section>', 1)[0]
    assert 'Coverage Source' in coverage
    assert 'Reference Scope' in coverage
    assert 'Backend Enumeration' in coverage
    assert 'Ready Reports' not in coverage
    assert 'Tracked Size' not in coverage

    governance = overview.split('data-storage-governance-contract="compact"', 1)[1].split('</aside>', 1)[0]
    assert 'Configuration Source' in governance
    assert 'Object Key Contract' in governance
    assert 'data-storage-object-key-contract="readable"' in governance
