from __future__ import annotations

from app.storage.object_storage.analytics.bucket_table import build_bucket_table_view


class _System:
    id = 42


ROWS = [
    {'name': 'healthy', 'quota_bytes': 100.0, 'quota_state': 'configured', 'quota_utilization': 21.5},
    {'name': 'pressure', 'quota_bytes': 100.0, 'quota_state': 'configured', 'quota_utilization': 89.0},
    {'name': 'critical', 'quota_bytes': 100.0, 'quota_state': 'configured', 'quota_utilization': 95.0},
    {'name': 'no-quota', 'quota_bytes': None, 'quota_state': 'not_configured', 'quota_utilization': None},
    {'name': 'unknown', 'quota_bytes': None, 'quota_state': 'not_collected', 'quota_utilization': None},
]


def view(**query: str) -> dict:
    return build_bucket_table_view(
        ROWS,
        query,
        page_key='capacity',
        system=_System(),
        time_range='6h',
    )


def test_capacity_quota_state_filter_is_source_qualified() -> None:
    assert [row['name'] for row in view(bucket_quota_state='configured')['rows']] == [
        'healthy',
        'pressure',
        'critical',
    ]
    assert [row['name'] for row in view(bucket_quota_state='not_configured')['rows']] == ['no-quota']
    assert [row['name'] for row in view(bucket_quota_state='unknown')['rows']] == ['unknown']


def test_capacity_pressure_filter_respects_existing_85_and_95_boundaries() -> None:
    for choice, expected in (
        ('within', 'healthy'),
        ('warning', 'pressure'),
        ('critical', 'critical'),
    ):
        result = view(bucket_quota_pressure=choice)
        assert [row['name'] for row in result['rows']] == [expected]
        assert result['quota_pressure'] == choice


def test_capacity_combined_filters_do_not_infer_pressure_for_unknown_quota() -> None:
    result = view(bucket_q='unknown', bucket_quota_state='unknown', bucket_quota_pressure='critical')
    assert result['rows'] == []
    assert result['pagination']['total_items'] == 0
    assert result['quota_state'] == 'unknown'
    assert result['query_params']['bucket_q'] == 'unknown'


def test_capacity_filter_pagination_preserves_rows_and_resets_out_of_range_page() -> None:
    result = view(bucket_quota_state='configured', bucket_page='99', bucket_per_page='10')
    assert result['pagination']['per_page'] == 10
    assert result['pagination']['page'] == 1
    assert result['pagination']['total_items'] == 3
    assert result['query_params']['bucket_quota_state'] == 'configured'
    assert result['query_params']['bucket_quota_pressure'] == 'all'
    assert result['query_params']['tab'] == 'quota'
    assert result['query_params']['time_range'] == '6h'


def test_invalid_quota_filters_fail_to_all_without_leaking_into_other_workspaces() -> None:
    result = view(bucket_quota_state='invalid', bucket_quota_pressure='bogus')
    assert result['quota_state'] == result['quota_pressure'] == 'all'
    assert len(result['rows']) == 5

    other = build_bucket_table_view(
        ROWS,
        {'bucket_quota_state': 'critical', 'bucket_quota_pressure': 'critical'},
        page_key='top_consumers',
        system=_System(),
        time_range='24h',
    )
    assert len(other['rows']) == 5
    assert 'bucket_quota_state' not in other['query_params']
    assert 'bucket_quota_pressure' not in other['query_params']


PERFORMANCE_ROWS = [
    {
        'name': 'metric-bucket',
        'usage_bytes': 120.0,
        'usage_source': 'Thanos Query',
        'request_rate': 2.0,
        'error_rate': 0.1,
    },
    {
        'name': 'inventory-bucket',
        'usage_bytes': 64.0,
        'usage_source': 'Committed Snapshot',
        'request_rate': None,
        'error_rate': None,
    },
    {
        'name': 'missing-bucket',
        'usage_bytes': None,
        'usage_source': 'Metric Not Scraped',
        'request_rate': None,
        'error_rate': None,
    },
]


def performance_view(**query: str) -> dict:
    return build_bucket_table_view(
        PERFORMANCE_ROWS,
        query,
        page_key='performance',
        system=_System(),
        time_range='12h',
    )


def test_performance_usage_context_filters_only_committed_bucket_usage_evidence() -> None:
    for context, expected in (
        ('metrics', 'metric-bucket'),
        ('inventory', 'inventory-bucket'),
        ('unavailable', 'missing-bucket'),
    ):
        result = performance_view(bucket_usage_context=context)
        assert [row['name'] for row in result['rows']] == [expected]
        assert result['usage_context'] == context
        assert result['query_params']['bucket_usage_context'] == context
        assert result['query_params']['tab'] == 'buckets'


def test_performance_usage_context_does_not_replace_missing_request_error_metrics() -> None:
    result = performance_view(bucket_usage_context='inventory')
    assert len(result['rows']) == 1
    assert result['rows'][0]['request_rate'] is None
    assert result['rows'][0]['error_rate'] is None


def test_performance_usage_context_combines_with_search_and_preserves_row_size() -> None:
    result = performance_view(bucket_q='metric', bucket_usage_context='inventory', bucket_per_page='10')
    assert result['rows'] == []
    assert result['pagination']['per_page'] == 10
    assert result['pagination']['total_items'] == 0
    assert result['query_params']['bucket_q'] == 'metric'
    assert result['query_params']['time_range'] == '12h'
    assert result['query_params']['bucket_usage_context'] == 'inventory'


def test_performance_invalid_usage_context_and_cross_workspace_isolation() -> None:
    invalid = performance_view(bucket_usage_context='unknown-option')
    assert invalid['usage_context'] == 'all'
    assert len(invalid['rows']) == 3

    other = build_bucket_table_view(
        PERFORMANCE_ROWS,
        {'bucket_usage_context': 'inventory'},
        page_key='top_consumers',
        system=_System(),
        time_range='6h',
    )
    assert len(other['rows']) == 3
    assert other['usage_context'] == 'all'
    assert 'bucket_usage_context' not in other['query_params']
