from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/reports/generate/index.html'
SERVICE = ROOT / 'app/reports/generate/service.py'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_generate_report_uses_canonical_hero_and_guided_full_width_builder() -> None:
    source = read(TEMPLATE)

    assert 'page_hero.shell_classes()' in source
    assert 'page_hero.layout_classes()' in source
    assert 'page_hero.content_classes()' in source
    assert 'page_hero.context_card(' in source
    assert 'Single Cluster Scope' in source
    assert 'Catalog-Driven Contract' in source
    assert 'Queued Artifact Generation' in source
    assert 'data-generate-report-workspace="guided-builder"' in source
    assert 'data-report-builder-progress="true"' in source
    assert 'Report Builder' in source
    assert 'xl:grid-cols-[minmax(0,1fr)_360px]' not in source
    assert 'xl:sticky xl:top-5 xl:self-start' not in source


def test_generate_report_uses_visual_family_and_report_contract_selection() -> None:
    source = read(TEMPLATE)

    assert 'data-report-family-filter="analytics"' in source
    assert 'data-report-family-filter="inventory"' in source
    assert 'data-report-type-card="{{ option.value }}"' in source
    assert 'data-report-family="{{ option.family }}"' in source
    assert 'id="report-type-card-grid"' in source
    assert 'id="report-type-select"' in source
    assert 'class="sr-only"' in source
    assert 'syncReportFamilyView' in source
    assert 'syncReportTypeCards' in source
    assert "reportTypeSelect.value = card.dataset.reportTypeCard;" in source
    assert 'Report Type Guide' not in source


def test_generate_report_is_structured_as_report_scope_artifact_review() -> None:
    source = read(TEMPLATE)

    for marker in (
        'data-generate-step="report"',
        'data-generate-step="scope"',
        'data-generate-step="artifact"',
        'data-generate-step="summary"',
    ):
        assert marker in source

    assert 'Choose Report' in source
    assert 'Define Scope' in source
    assert 'Configure Artifact' in source
    assert 'Review & Queue' in source
    assert 'Create & Queue Report' in source
    assert 'Scope Boundary' in source


def test_generate_report_removes_duplicate_guide_and_sidebar_content() -> None:
    source = read(TEMPLATE)
    service = read(SERVICE)

    for legacy in (
        'Report Type Guide',
        'Generation Guide',
        'Storage Context',
        'Generation Readiness',
        'Request Preview',
        'Follow the governed request-to-artifact flow.',
    ):
        assert legacy not in source

    assert 'components/info_flow.html' not in source
    assert 'components/related_page_card.html' not in source
    assert "'generation_flow': _get_generation_flow()" not in service
    assert "'report_type_guide_groups': _get_report_type_guide_groups()" not in service
    assert "'recommended_actions': _get_recommended_actions()" not in service
    assert "'readiness': _get_generation_readiness(" not in service
    assert 'def _get_generation_flow' not in service
    assert 'def _get_report_type_guide_groups' not in service
    assert 'def _get_recommended_actions' not in service
    assert 'def _get_generation_readiness' not in service


def test_inventory_sections_are_contract_locked_without_disabled_checkboxes() -> None:
    source = read(TEMPLATE)

    assert "payload.selected_report_type.family == 'inventory'" in source
    assert 'Inventory workbook structure is locked by the report contract.' in source
    assert '<input type="hidden" name="sections" value="{{ section.value }}">' in source
    assert "input.type = 'hidden';" in source
    assert "marker.innerHTML = '<i data-lucide=\"file-spreadsheet\"" in source
    assert "input.disabled = inventoryContractLocked" not in source
    assert "setElementVisibility(selectionActions, !inventoryContractLocked);" in source


def test_output_format_is_visual_and_period_options_follow_selected_contract() -> None:
    source = read(TEMPLATE)

    assert 'option.value in payload.selected_report_type.allowed_formats' in source
    assert '{% if not format_allowed %}disabled hidden{% endif %}' in source
    assert 'data-output-format-card="{{ option.value }}"' in source
    assert 'data-output-format-grid="true"' in source
    assert 'syncOutputFormatCards' in source
    assert "outputFormatSelect.value = card.dataset.outputFormatCard;" in source
    assert 'option.disabled = !isAllowed;' in source
    assert 'option.hidden = !isAllowed;' in source
    assert "option.value !== 'snapshot'" in source
    assert "option.value === 'snapshot'" in source
    assert 'Analytics: PDF / CSV · Inventory: XLSX / CSV' in source


def test_generate_report_uses_semantic_status_tokens_and_preserves_storage_guard() -> None:
    source = read(TEMPLATE)
    service = read(SERVICE)

    assert 'border-status-critical-border bg-status-critical-soft' in source
    assert 'border-status-warning-border bg-status-warning-soft' in source
    assert 'border-rose-200' not in source
    assert 'border-amber-200' not in source
    assert 'payload.generation_allowed' in source
    assert 'storageGenerationReady' in source
    assert 'Artifact Storage Needs Review' in source
    assert 'storage_status = get_report_storage_backend_status()' in service
    assert "if not bool(storage_status.get('write_available', False))" in service


def test_review_manifest_keeps_dynamic_contract_ids_for_runtime_sync() -> None:
    source = read(TEMPLATE)

    for element_id in (
        'report-type-select',
        'report-name-input',
        'cluster-select',
        'namespace-select',
        'period-select',
        'output-format-select',
        'selected-section-list',
        'selected-section-count-badge',
        'preview-report-type',
        'preview-report-name',
        'preview-cluster',
        'preview-namespace',
        'preview-period',
        'preview-output-format',
        'preview-sections',
        'preview-included-sections',
        'readiness-scope-status',
        'readiness-sections-status',
        'preview-eligibility-status',
        'generate-report-button',
    ):
        assert f'id="{element_id}"' in source

    assert 'syncReportTypeSummary' in source
    assert 'syncOutputFormatMode' in source
    assert 'syncPeriodMode' in source
    assert 'syncClusterGuard' in source
    assert 'renderSectionList' in source
