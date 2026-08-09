from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVICE = ROOT / 'app/reports/generated/service.py'
DETAIL = ROOT / 'app/templates/reports/generated/detail.html'
GENERATE = ROOT / 'app/templates/reports/generate/index.html'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_generated_registry_is_metadata_first_and_avoids_global_storage_integrity_scans() -> None:
    service = read(SERVICE)

    payload_block = service.split('def get_generated_reports_payload(', 1)[1].split(
        'def get_report_detail_payload(', 1
    )[0]
    assert "'lifecycle_status': get_lifecycle_status()" not in payload_block
    assert "'storage_context': get_storage_context()" not in payload_block
    assert "'hero_posture': get_hero_posture()" not in payload_block
    assert 'backend_status=backend_status' in payload_block

    get_reports_block = service.split('def get_reports(', 1)[1].split('def get_pagination(', 1)[0]
    assert 'verify_artifact=False' in get_reports_block
    assert 'active_backend_status=backend_status' in get_reports_block
    assert '_summarize_report_file_reference' in service
    assert 'without per-row object-storage HEAD checks' in service


def test_generated_detail_separates_retained_artifact_from_latest_generation_attempt() -> None:
    template = read(DETAIL)

    assert 'data-generated-report-detail="operator-record-v2"' in template
    assert 'data-generated-detail-block="artifact-record"' in template
    assert 'data-generated-detail-block="generation-timeline"' in template
    assert 'data-generated-detail-block="report-contract"' in template
    assert 'data-generated-detail-lifecycle-actions="true"' in template

    assert 'Artifact Record' in template
    assert 'Generation Timeline' in template
    assert 'Latest Attempt' in template
    assert 'Report Contract' in template
    assert 'Evidence Boundary' in template
    assert 'Storage Reference' in template

    assert 'data-generated-detail-regeneration-state="active-retained"' in template
    assert 'data-generated-detail-regeneration-state="failed-retained"' in template
    assert 'Regeneration In Progress' in template
    assert 'Verified Artifact Retained' in template
    assert 'The existing verified artifact remains available while the latest generation attempt runs.' in template
    assert 'The latest generation attempt failed, but the previously verified artifact remains available for download.' in template

    assert 'Artifact availability is evaluated separately from the latest generation attempt.' in template
    assert 'Regeneration reuses this persisted request contract' in template
    assert 'Existing verified artifacts remain available if a regeneration attempt fails.' in template

    assert 'data-generation-timeline="true"' in template
    assert "('01', 'Requested'" in template
    assert "('02', 'Queued'" in template
    assert "('03', 'Started'" in template
    assert "('04', 'Completed'" in template

    assert 'xl:grid-cols-[minmax(0,1fr)_380px]' not in template
    assert 'Status Context' not in template
    assert 'Export Readiness' not in template
    assert 'Recommended Actions' not in template
    assert 'Generation Evidence & Report Content' not in template
    assert 'bg-rose-' not in template
    assert 'bg-emerald-' not in template


def test_generated_detail_lifecycle_actions_use_single_click_operation_guard() -> None:
    template = read(DETAIL)

    assert 'data-loading-label="Queueing generation..."' in template
    assert 'data-loading-label="Archiving..."' in template
    assert 'data-loading-label="Restoring..."' in template
    assert template.count('data-operation-submit') >= 3
    assert template.count('data-operation-submit-label') >= 3


def test_generate_review_status_is_grouped_with_readiness_and_submit_is_single_click_safe() -> None:
    template = read(GENERATE)

    review_header = template.split('data-generate-section-header="review-queue"', 1)[1].split(
        '<div class="mt-3 grid', 1
    )[0]
    assert 'preview-eligibility-status' not in review_header

    readiness_block = template.split('aria-label="Request readiness"', 1)[1].split('</div>', 1)[0]
    assert 'preview-eligibility-status' in readiness_block
    assert 'Action Required' in template
    assert 'Ready to Queue' in template

    button_block = template.split('id="generate-report-button"', 1)[1].split('</button>', 1)[0]
    assert 'data-operation-submit' in button_block
    assert 'data-loading-label="Queueing report..."' in button_block
    assert 'data-operation-submit-label' in button_block
