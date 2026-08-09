from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / 'app/templates/reports/generate/index.html'
SERVICE = ROOT / 'app/reports/generate/service.py'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_generate_report_uses_canonical_hero_and_compact_operator_workspace() -> None:
    source = read(TEMPLATE)

    assert 'page_hero.shell_classes()' in source
    assert 'page_hero.layout_classes()' in source
    assert 'page_hero.content_classes()' in source
    assert 'page_hero.context_card(' in source
    assert 'Single Cluster Scope' in source
    assert 'Catalog-Driven Contract' in source
    assert 'Queued Artifact Generation' in source
    assert 'data-generate-report-workspace="compact-operator-workspace"' in source
    assert 'Configure Report Request' in source
    assert 'data-report-builder-progress="true"' not in source
    assert 'Report Builder' not in source
    assert 'xl:grid-cols-[minmax(0,1fr)_360px]' not in source
    assert 'xl:sticky xl:top-5 xl:self-start' not in source


def test_report_selection_is_compact_catalog_select_not_card_wall() -> None:
    source = read(TEMPLATE)

    assert 'id="report-type-select"' in source
    assert "('analytics', 'Kubernetes Analytics')" in source
    assert "('inventory', 'Kubernetes Inventory')" in source
    assert 'id="selected-template-summary"' in source
    assert 'data-report-type-card=' not in source
    assert 'data-report-family-filter=' not in source
    assert 'id="report-type-card-grid"' not in source
    assert 'class="sr-only"' not in source.split('id="report-type-select"', 1)[0][-300:]
    assert 'Report Type Guide' not in source


def test_generate_report_uses_two_primary_configuration_zones_and_compact_review() -> None:
    source = read(TEMPLATE)

    for marker in (
        'data-generate-step="report"',
        'data-generate-step="scope"',
        'data-generate-step="artifact"',
        'data-generate-step="summary"',
    ):
        assert marker in source

    assert 'Report Contract' in source
    assert 'Kubernetes Scope' in source
    assert 'Report Content' in source
    assert 'Review & Queue' in source
    assert 'Review the request summary before it is queued for artifact generation.' in source
    assert 'aria-label="Request readiness"' in source
    review_header = source.split('data-generate-section-header="review-queue"', 1)[1].split('<div class="mt-3 grid', 1)[0]
    assert 'preview-eligibility-status' not in review_header
    assert 'Create & Queue Report' in source
    assert 'xl:grid-cols-2 xl:divide-x xl:divide-outline-default' in source
    assert '01 Choose Report' not in source
    assert '02 Define Scope' not in source
    assert '03 Configure Artifact' not in source


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


def test_inventory_sections_are_contract_locked_and_compact() -> None:
    source = read(TEMPLATE)

    assert "payload.selected_report_type.family == 'inventory'" in source
    assert 'Workbook structure is locked by the report contract.' in source
    assert '<input type="hidden" name="sections" value="{{ section.value }}">' in source
    assert "input.type = 'hidden';" in source
    assert 'sm:grid-cols-3' in source
    assert "marker.innerHTML = '<i data-lucide=\"file-spreadsheet\"" in source
    assert "input.disabled = inventoryContractLocked" not in source
    assert "setElementVisibility(selectionActions, !inventoryContractLocked);" in source


def test_output_format_uses_compact_native_select_and_contract_filtering() -> None:
    source = read(TEMPLATE)

    assert 'id="output-format-select"' in source
    assert 'option.value in payload.selected_report_type.allowed_formats' in source
    assert '{% if not format_allowed %}disabled hidden{% endif %}' in source
    assert 'data-output-format-card=' not in source
    assert 'data-output-format-grid=' not in source
    assert 'option.disabled = !isAllowed;' in source
    assert 'option.hidden = !isAllowed;' in source
    assert "option.value !== 'snapshot'" in source
    assert "option.value === 'snapshot'" in source
    assert 'Supported Formats' in source
    assert 'id="output-format-contract"' in source
    assert "allowedFormats\n                            .map(function (format) { return format.toUpperCase(); })" in source


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


def test_compact_review_keeps_dynamic_contract_ids_for_runtime_sync() -> None:
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


def test_generate_report_typography_and_summary_are_visually_hierarchical() -> None:
    source = read(TEMPLATE)

    for heading in (
        'Report Contract',
        'Kubernetes Scope',
        'Artifact',
        'Report Content',
        'Review & Queue',
    ):
        assert f'class="text-base font-bold text-content-primary">{heading}</h3>' in source

    assert 'text-[10px]' not in source
    assert 'text-[11px]' not in source
    assert 'id="preview-report-type"' in source
    assert 'id="preview-cluster"' in source
    assert 'id="preview-output-format"' in source
    assert 'sm:grid-cols-3' in source
    assert 'Select a specific cluster to load namespace options.' not in source
    assert 'Cluster selection loads namespace options.' not in source
    assert 'id="namespace-select-help"' not in source
    assert 'Supported Formats' in source
    assert 'id="output-format-contract"' in source


def test_scope_filters_are_symmetric_and_use_guidance_instead_of_inline_warning() -> None:
    source = read(TEMPLATE)

    assert 'data-scope-filter="namespace"' in source
    assert 'data-scope-filter="period"' in source
    assert source.count('flex min-h-5 items-center justify-between gap-2') >= 2
    assert 'id="period-mode-label"' in source
    assert "periodModeLabel.textContent = isInventoryReport ? 'Snapshot' : 'Time Range';" in source
    assert 'data-generate-scope-tip="true"' in source
    assert 'Scope Tip' in source
    assert 'Choose a cluster to unlock namespace selection.' in source
    assert 'All Namespaces' in source
    assert 'Select a cluster before queueing.' not in source
    assert 'id="cluster-guard"' not in source
    assert "const clusterGuard = document.getElementById('cluster-guard');" not in source
    assert 'setElementVisibility(clusterGuard, shouldBlockCluster);' not in source


def test_generate_report_uses_numbered_workflow_hierarchy_without_progress_rail() -> None:
    source = read(TEMPLATE)

    expected = {
        'report-contract': '01',
        'kubernetes-scope': '02',
        'artifact': '03',
        'report-content': '04',
        'review-queue': '05',
    }
    for section, number in expected.items():
        assert f'data-generate-section-header="{section}"' in source
        assert f"workflow_number('{number}')" in source

    assert 'data-selected-report-summary="true"' in source
    assert "context_icon_marker('file-check-2')" in source
    assert 'data-generate-context-marker="{{ icon_name }}"' in source
    assert "workflow_number('01', true)" not in source
    assert 'Selected Report' in source
    assert 'selectedReportIcon' not in source
    assert 'id="selected-report-icon"' not in source
    assert 'data-report-builder-progress="true"' not in source
    macro = source.split('{% macro workflow_number', 1)[1].split('{%- endmacro %}', 1)[0]
    assert 'rounded-lg' in macro
    assert 'rounded-full' not in macro
