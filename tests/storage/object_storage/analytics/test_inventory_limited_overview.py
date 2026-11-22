"""Inventory-only Object Storage Analytics cannot fabricate operational metrics (#5124)."""

from pathlib import Path

from jinja2 import Environment

from app.storage.object_storage.analytics.inventory_limited import inventory_limited_coverage

ROOT = Path(__file__).resolve().parents[4]


def test_inventory_limited_coverage_distinguishes_observed_zero_from_unknown() -> None:
    empty = inventory_limited_coverage(
        bucket_count=0,
        size_observed=0,
        size_total=None,
        objects_observed=0,
        objects_total=None,
    )
    assert empty['bucket_count_display'] == '0'
    assert empty['size_status'] == 'Observed'
    assert empty['objects_status'] == 'Observed'
    assert empty['objects_display'] == '0'

    missing = inventory_limited_coverage(
        bucket_count=3,
        size_observed=1,
        size_total=1024,
        objects_observed=0,
        objects_total=None,
    )
    assert missing['bucket_count_display'] == '3'
    assert missing['size_display'] == 'N/A'
    assert missing['objects_display'] == 'N/A'
    assert missing['size_status'] == 'Incomplete'
    assert missing['objects_status'] == 'Incomplete'
    assert missing['size_coverage'] == '1 / 3 buckets'


def test_inventory_limited_complete_aggregates_are_observed_not_metric_estimates() -> None:
    complete = inventory_limited_coverage(
        bucket_count=2,
        size_observed=2,
        size_total=1536,
        objects_observed=2,
        objects_total=7,
    )
    assert complete['bucket_count_display'] == '2'
    assert complete['size_display'] != 'N/A'
    assert complete['objects_display'] == '7'
    assert complete['size_status'] == 'Observed'
    assert complete['objects_status'] == 'Observed'


def test_limited_overview_preserves_worker_and_committed_inventory_boundaries() -> None:
    service = (ROOT / 'app/storage/object_storage/analytics/service.py').read_text()
    inventory_service = (ROOT / 'app/storage/object_storage/analytics/inventory_limited.py').read_text()
    overview = (ROOT / 'app/templates/storage/object_storage/analytics/index.html').read_text()
    limited = (
        ROOT / 'app/templates/storage/object_storage/analytics/partials/_overview_inventory_limited.html'
    ).read_text()
    posture = (ROOT / 'app/templates/storage/object_storage/analytics/partials/_hero_posture.html').read_text()

    for text in (overview, limited, posture):
        Environment().parse(text)

    assert 'if system.inventory_observed_at is None:' in service
    assert "context['inventory_limited'] = build_inventory_limited_view(system)" in inventory_service
    assert 'ObjectStorageBucket.object_storage_system_id == system.id' in inventory_service
    assert "context['dependency_blocker'] = None" in inventory_service
    assert 'data-object-storage-inventory-limited-overview' in limited
    assert 'inventory_limited.size_display' in limited
    assert 'inventory_limited.objects_display' in limited
    assert "metrics_source'] = {" in inventory_service
    assert 'Not Collected' in limited or 'Not Collected' in inventory_service
    assert "if page_key == 'overview' and analytics_limited" in posture
    assert 'if analytics_limited' in overview
    assert 'storage/object_storage/analytics/partials/_overview_analysis.html' in overview
    assert 'storage/object_storage/analytics/partials/_overview_workspace.html' in overview
