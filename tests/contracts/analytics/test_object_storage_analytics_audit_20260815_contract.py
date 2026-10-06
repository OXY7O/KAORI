from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_object_storage_hero_copy_is_specific_without_becoming_verbose() -> None:
    pages = read('app/storage/object_storage/analytics/pages.py')

    expected = (
        'Review capacity, bucket pressure, quotas, trends, and growth.',
        'Review S3 activity, errors, queue depth, demand, and traffic.',
        'Project storage growth and exhaustion risk from committed history.',
        'Rank buckets by storage, objects, requests, and concentration.',
    )
    for copy in expected:
        assert copy in pages
        words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*", copy)
        assert 7 <= len(words) <= 15
        assert len(copy) <= 68


def test_object_storage_blocker_reuses_kubernetes_analytics_dependency_surface() -> None:
    object_blocker = read('app/templates/storage/object_storage/analytics/partials/_dependency_blocker.html')
    shared_blocker = read('app/templates/components/dependencies/_blocker.html')
    blocked_hero = read('app/templates/storage/object_storage/analytics/partials/_hero_blocked_posture.html')

    assert 'components/dependencies/_blocker.html' in object_blocker
    assert 'Object Storage → Metrics → Analytics Snapshot' in object_blocker
    assert 'Alert Evidence' not in object_blocker
    assert object_blocker.count('dependency_grid_classes = "lg:grid-cols-3"') == 2
    assert 'Analytics Setup Path' in shared_blocker
    assert 'Current Blocker' in shared_blocker
    assert 'Missing dependency:' in shared_blocker
    assert 'dependency_route_summary' in shared_blocker
    assert 'dependency_step_count' in shared_blocker
    assert "'Analytics Readiness'" in blocked_hero
    assert "'Active Scope'" in blocked_hero
    assert "'Missing Evidence'" in blocked_hero
    assert "'Current Step'" not in blocked_hero
    assert "'Progress'" not in blocked_hero


def test_object_storage_analytics_requires_committed_inventory_before_metrics_analysis() -> None:
    dependencies = read('app/storage/object_storage/analytics/dependencies.py')
    service = read('app/storage/object_storage/analytics/service.py')

    assert "'inventory_required'" in dependencies
    assert 'Object Storage Inventory Sync Required' in dependencies
    assert "'action_endpoint': 'object_storage_inventory.overview'" in dependencies
    assert service.count('if system.inventory_observed_at is None:') >= 1
    assert service.count('inventory_required_blocker(system)') >= 1
    assert "return get_object_storage_analytics_context('alerts', query_args)" in service
    assert 'return get_object_storage_analytics_context(page_key, query_args)' in service


def test_object_storage_runtime_boundary_stays_provider_neutral_and_fail_fast() -> None:
    routes = read('app/storage/object_storage/analytics/routes.py')
    service = read('app/storage/object_storage/analytics/service.py')
    runtime = read('app/storage/object_storage/analytics/runtime.py')
    materialization = read('app/storage/object_storage/analytics/materialization.py')

    assert routes.count("@permission_required('object_storage_analytics.view')") == 10
    for forbidden in ('MetricsConsumer(', 'MinioClient(', 'boto3', 'minio.client'):
        assert forbidden not in routes
        assert forbidden not in service
        assert forbidden not in runtime
    assert 'source_wide_failure' in runtime
    assert 'failed_query_count' in runtime
    assert 'successful_query_count' in runtime
    assert "execution_mode='background'" in materialization
    assert 'ObjectStorageForecastSnapshot' in materialization


def test_object_storage_alert_and_metric_evidence_paths_remain_independent() -> None:
    service = read('app/storage/object_storage/analytics/service.py')
    alerts = read('app/storage/object_storage/analytics/alert_sources.py')
    workspace = read('app/templates/storage/object_storage/analytics/partials/_alerts_workspace.html')

    assert 'alerts_evidence_available' in service
    assert 'alerts_degraded' in service
    assert "ALERT_SOURCE_OPTIONS = ('auto', 'alertmanager', 'metrics_source')" in alerts
    assert 'Metrics Source Fallback Active' in alerts
    assert 'Provider Alerts' in workspace
    assert 'Anomaly Signals' in workspace
    assert 'Recommendations' in workspace


def test_object_storage_htmx_record_fragments_fail_closed_on_dependency_loss() -> None:
    bucket_table = read('app/templates/storage/object_storage/analytics/partials/_bucket_table.html')
    alert_records = read('app/templates/storage/object_storage/analytics/partials/_alert_records.html')
    notice = read('app/templates/storage/object_storage/analytics/partials/_dependency_notice.html')

    assert '{% if dependency_blocker %}' in bucket_table
    assert '_dependency_notice.html' in bucket_table
    assert '{% if dependency_blocker %}' in alert_records
    assert '_dependency_notice.html' in alert_records
    assert 'dependency_blocker.title' in notice
    assert 'dependency_blocker.description' in notice
    assert 'dependency_blocker.diagnostic_detail' in notice
