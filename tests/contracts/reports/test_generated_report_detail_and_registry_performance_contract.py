from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVICE = ROOT / 'app/reports/generated/service.py'
DETAIL = ROOT / 'app/templates/reports/generated/detail.html'
REGISTRY = ROOT / 'app/templates/reports/generated/index.html'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_generated_detail_uses_operational_dossier_hierarchy() -> None:
    template = read(DETAIL)

    assert 'data-generated-report-detail="operational-dossier-v5"' in template
    assert 'data-generated-detail-block="report-overview"' in template
    assert 'data-generated-detail-block="generation-evidence"' in template
    assert 'data-generated-detail-report-actions="true"' in template
    assert 'data-generated-detail-polish="professional-v1"' in template
    assert 'data-report-overview-grid="true"' in template
    assert 'data-report-overview-layout="balanced-dossier"' in template
    assert 'data-generated-evidence-layout="stacked-bands-v2"' in template
    assert 'data-generated-detail-actions-embedded="true"' in template

    assert 'Report Overview' in template
    assert 'Report Context' in template
    assert 'Governed Evidence Scope' in template
    assert 'Artifact Delivery' in template
    assert 'Technical Storage Reference' in template
    assert 'View Storage Reference' in template
    assert 'Storage Reference' in template
    assert 'Generation & Evidence' in template
    assert 'Latest Generation Attempt' in template
    assert 'Persisted Report Definition' in template
    assert 'Governed Evidence Scope' in template
    assert 'data-generated-detail-report-actions="true"' in template

    for old_label in [
        'Artifact Record',
        'Generation Timeline',
        'Report Content & Evidence',
        'Lifecycle Actions',
    ]:
        assert old_label not in template


def test_generated_detail_regeneration_state_keeps_artifact_and_attempt_separate() -> None:
    template = read(DETAIL)

    assert 'data-generated-detail-regeneration-state="active-retained"' in template
    assert 'data-generated-detail-regeneration-state="failed-retained"' in template
    assert 'Regeneration In Progress' in template
    assert 'Latest Regeneration Failed' in template
    assert 'Verified Artifact Available' in template
    assert 'The verified artifact remains available while the latest regeneration attempt is running.' in template
    assert 'The latest attempt failed, but the previously verified artifact is still available for download.' in template
    assert 'Artifact availability is evaluated independently from the latest generation attempt.' in template
    assert 'data-generated-detail-actions-embedded="true"' in template


def test_generated_detail_visible_labels_follow_title_case_standard() -> None:
    template = read(DETAIL)
    service = read(SERVICE)

    required_title_case = [
        'Generated Report',
        'Delivery Posture',
        'Report Status',
        'Report Context',
        'Governed Evidence Scope',
        'Artifact Delivery',
        'Generation & Evidence',
        'Latest Generation Attempt',
        'Persisted Report Definition',
        'Governed Evidence Scope',
        'Back to Registry',
    ]
    for label in required_title_case:
        assert label in template

    assert "'24h': 'Last 24 Hours'" in service
    assert "'7d': 'Last 7 Days'" in service
    assert "'30d': 'Last 30 Days'" in service
    assert "'90d': 'Last 90 Days'" in service
    assert "'month': 'This Month'" in service

    for label in [
        'Storage Unavailable',
        'Missing File',
        'File Path Missing',
        'Archived Artifact',
        'Archived Artifact Missing',
        'Archived Without Artifact',
        'Not Available',
        'Not Generated',
    ]:
        assert label in service


def test_generated_detail_lifecycle_and_actions_remain_single_click_safe() -> None:
    template = read(DETAIL)

    assert "('01', 'Requested'" in template
    assert "('02', 'Queued'" in template
    assert "('03', 'Started'" in template
    assert "('04', 'Completed'" in template
    assert 'data-generation-lifecycle="true"' in template
    assert 'data-generated-detail-latest-attempt-panel="true"' in template
    assert 'data-generated-detail-definition-panel="true"' in template
    assert 'data-generated-detail-actions-embedded="true"' in template
    assert 'id="report-actions"' in template

    assert 'data-loading-label="Queueing Generation..."' in template
    assert 'data-loading-label="Archiving Report..."' in template
    assert 'data-loading-label="Restoring Report..."' in template
    assert template.count('data-operation-submit') >= 3
    assert template.count('data-operation-submit-label') >= 3

    assert 'xl:grid-cols-[minmax(0,1fr)_380px]' not in template
    assert 'lg:divide-x lg:divide-outline-subtle' not in template
    assert 'data-report-context="true"' in template
    assert 'data-artifact-delivery-panel="true"' in template
    assert '{% import "integrations/components/_record_detail_modal.html" as record_detail_modal %}' in template
    assert 'record_detail_modal.render(' in template
    assert "size='standard'" in template
    assert 'data-kaori-dialog-open' in template
    assert 'data-dialog-target="{{ storage_reference_modal_id }}"' in template
    assert 'data-generated-storage-reference-modal="true"' in template
    assert 'data-storage-reference-handoff="true"' in template
    assert 'data-storage-reference-technical-evidence="true"' in template
    assert '<details class="group mt-4' not in template
    assert 'data-generated-attempt-interpretation="true"' in template
    assert 'Artifact and Attempt Are Independent' in template
    assert 'data-generated-definition-scope="true"' in template
    assert "status_indicator_label('Archived', 'warning')" not in template
    assert 'data-generated-detail-primary-action="restore"' in template
    assert 'data-generated-detail-primary-action="download"' in template
    assert 'bg-rose-' not in template
    assert 'bg-emerald-' not in template


def test_storage_reference_uses_shared_native_modal_and_attempt_layout_has_no_dead_column() -> None:
    template = read(DETAIL)

    assert 'storage_reference_modal_id' in template
    assert 'View Storage Reference' in template
    assert 'aria-haspopup="dialog"' in template
    assert 'data-generated-storage-reference-open' in template
    assert 'Generated Report Storage Evidence' in template
    assert 'Artifact Delivery Context' in template
    assert 'Technical Reference' in template
    assert 'Reference Boundary' in template
    assert 'Storage URI' in template
    assert 'Object Key' in template

    # Attempt evidence is a full-width horizontal band; persisted definition follows below.
    assert 'data-generated-evidence-layout="stacked-bands-v2"' in template
    assert 'data-generated-evidence-columns="true"' not in template
    assert 'xl:border-r xl:border-outline-subtle xl:pb-0 xl:pr-7' not in template
    assert 'Artifact availability is evaluated independently from the latest generation attempt.' in template



def test_registry_report_identity_has_domain_icon_and_service_mapping() -> None:
    template = read(REGISTRY)
    service = read(SERVICE)

    assert 'data-generated-report-identity="true"' in template
    assert 'data-generated-report-icon="{{ report.report_icon }}"' in template
    assert 'data-lucide="{{ report.report_icon }}"' in template
    assert "'report_icon': _get_report_visual_icon(report.report_type)" in service
    assert 'def _get_report_visual_icon(value: str) -> str:' in service
    assert "return 'boxes'" in service
    assert "return 'siren'" in service
    assert "return 'trending-up'" in service
    assert "return 'hard-drive'" in service
    assert "return 'file-text'" in service
