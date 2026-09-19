from app.storage.object_storage.inventory.presentation import (
    _format_bytes,
    _format_count,
    _quota_view,
    _usage_collection_label,
    _usage_mode_label,
)


def test_bucket_usage_formatters_are_compact() -> None:
    assert _format_bytes(None) == 'Not Collected'
    assert _format_bytes(1024**3) == '1.00 GiB'
    assert _format_count(None) == 'Not Collected'
    assert _format_count(1234567) == '1,234,567'


def test_bucket_quota_presentation_distinguishes_configuration_states() -> None:
    configured = _quota_view(10 * 1024**3, 'configured')
    assert configured['label'] == '10.00 GiB'
    assert configured['state_label'] == 'Configured'
    assert configured['tone'] == 'normal'

    no_quota = _quota_view(None, 'not_configured')
    assert no_quota['label'] == 'No Quota'
    assert no_quota['state_label'] == 'Not Configured'

    missing = _quota_view(None, 'not_collected')
    assert missing['label'] == 'Not Collected'


def test_quota_evidence_presentation_maps_access_denied_to_actionable_guidance() -> None:
    from app.storage.object_storage.inventory.presentation import _quota_evidence_view

    evidence = _quota_evidence_view(
        'access_denied',
        quota_state='not_collected',
        metadata={'quota_evidence': {'status_code': 403, 'provider_code': 'AccessDenied'}},
    )

    assert evidence['label'] == 'Access Denied'
    assert evidence['tone'] == 'warning'
    assert 'admin:GetBucketQuota' in evidence['guidance']
    assert evidence['supporting'] == 'HTTP 403 · AccessDenied'


def test_quota_evidence_presentation_maps_provider_routing_failure() -> None:
    from app.storage.object_storage.inventory.presentation import _quota_evidence_view

    evidence = _quota_evidence_view(
        'admin_api_unreachable',
        quota_state='not_collected',
        metadata={},
    )

    assert evidence['label'] == 'Admin API Unreachable'
    assert '/minio/admin/*' in evidence['guidance']


def test_usage_presentation_distinguishes_provider_metrics_source() -> None:
    metadata = {
        'usage_stats_mode': 'provider_metrics',
        'usage_collection': 'minio_admin_data_usage_v3',
    }
    assert _usage_mode_label(metadata) == 'Provider Metrics'
    assert _usage_collection_label(metadata) == 'MinIO Admin Data Usage v3'

    fallback = {
        'usage_stats_mode': 'full_scan',
        'usage_collection': 's3_list_objects_v2',
    }
    assert _usage_mode_label(fallback) == 'Full Scan'
    assert _usage_collection_label(fallback) == 'S3 ListObjectsV2'
