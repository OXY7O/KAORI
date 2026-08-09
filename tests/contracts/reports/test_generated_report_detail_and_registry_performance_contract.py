from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVICE = ROOT / 'app/reports/generated/service.py'
DETAIL = ROOT / 'app/templates/reports/generated/detail.html'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_generated_detail_uses_refined_operator_hierarchy() -> None:
    template = read(DETAIL)

    assert 'data-generated-report-detail="operator-record-v3"' in template
    assert 'data-generated-detail-block="report-overview"' in template
    assert 'data-generated-detail-block="generation-lifecycle"' in template
    assert 'data-generated-detail-block="report-content-evidence"' in template
    assert 'data-generated-detail-report-actions="true"' in template

    assert 'Report Overview' in template
    assert 'Report Identity & Scope' in template
    assert 'Artifact Delivery' in template
    assert 'Generation Lifecycle' in template
    assert 'Latest Attempt' in template
    assert 'Report Content & Evidence' in template
    assert 'Included Sections' in template
    assert 'Evidence Scope' in template
    assert 'Governed Evidence Scope' in template
    assert 'Report Actions' in template

    assert 'Artifact Record' not in template
    assert 'Generation Timeline' not in template
    assert 'Lifecycle Actions' not in template
    assert 'Evidence Boundary' not in template
    assert 'data-generation-timeline="true"' not in template
    assert 'data-generation-lifecycle="true"' in template


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
    assert 'Regeneration preserves the existing verified artifact if the latest attempt fails.' in template


def test_generated_detail_visible_labels_follow_title_case_standard() -> None:
    template = read(DETAIL)
    service = read(SERVICE)

    required_title_case = [
        'Generated Report',
        'Artifact Status',
        'Report Overview',
        'Report Identity & Scope',
        'Artifact Delivery',
        'Generation Lifecycle',
        'Latest Attempt',
        'Attempt Status',
        'Report Content & Evidence',
        'Included Sections',
        'Evidence Scope',
        'Governed Evidence Scope',
        'Report Actions',
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


def test_generated_detail_timeline_and_actions_remain_single_click_safe() -> None:
    template = read(DETAIL)

    assert "('01', 'Requested'" in template
    assert "('02', 'Queued'" in template
    assert "('03', 'Started'" in template
    assert "('04', 'Completed'" in template

    assert 'data-loading-label="Queueing Generation..."' in template
    assert 'data-loading-label="Archiving Report..."' in template
    assert 'data-loading-label="Restoring Report..."' in template
    assert template.count('data-operation-submit') >= 3
    assert template.count('data-operation-submit-label') >= 3

    assert 'xl:grid-cols-[minmax(0,1fr)_380px]' not in template
    assert 'bg-rose-' not in template
    assert 'bg-emerald-' not in template
