from __future__ import annotations

from app.storage.object_storage.analytics.bucket_table import (
    build_bucket_forecast_table_view,
    build_bucket_table_view,
)


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


def test_invalid_quota_filters_and_top_consumer_scoping_do_not_leak_to_performance() -> None:
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
    assert [row['name'] for row in other['rows']] == ['critical']
    assert other['quota_state'] == 'all'
    assert other['quota_pressure'] == 'critical'
    assert other['query_params']['bucket_quota_state'] == 'all'
    assert other['query_params']['bucket_quota_pressure'] == 'critical'

    performance = build_bucket_table_view(
        ROWS,
        {'bucket_quota_state': 'configured', 'bucket_quota_pressure': 'critical'},
        page_key='performance',
        system=_System(),
        time_range='24h',
    )
    assert len(performance['rows']) == 5
    assert 'bucket_quota_state' not in performance['query_params']
    assert 'bucket_quota_pressure' not in performance['query_params']


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


def test_performance_invalid_usage_context_and_top_consumer_usage_filter_isolation() -> None:
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
    assert [row['name'] for row in other['rows']] == ['inventory-bucket']
    assert other['usage_context'] == 'inventory'
    assert other['query_params']['bucket_usage_context'] == 'inventory'

    capacity = build_bucket_table_view(
        PERFORMANCE_ROWS,
        {'bucket_usage_context': 'inventory'},
        page_key='capacity',
        system=_System(),
        time_range='6h',
    )
    assert len(capacity['rows']) == 3
    assert capacity['usage_context'] == 'all'
    assert 'bucket_usage_context' not in capacity['query_params']


FORECAST_ROWS = [
    {'name': 'ready-warning', 'watch_tone': 'warning', 'history_state': 'ready'},
    {'name': 'baseline-missing', 'watch_tone': 'normal', 'history_state': 'no_data'},
    {'name': 'baseline-partial', 'watch_tone': 'normal', 'history_state': 'partial'},
]


def forecast_view(**query: str) -> dict:
    return build_bucket_forecast_table_view(
        FORECAST_ROWS,
        query,
        system=_System(),
        history_window='30d',
    )


def test_forecast_watch_and_history_filter_intersect_on_committed_records() -> None:
    result = forecast_view(forecast_watch='normal', forecast_history_state='no_data')
    assert [row['name'] for row in result['rows']] == ['baseline-missing']
    assert result['pagination']['total_items'] == 1
    assert result['watch'] == 'normal'
    assert result['history_state'] == 'no_data'
    assert result['query_params']['forecast_watch'] == 'normal'
    assert result['query_params']['forecast_history_state'] == 'no_data'


def test_forecast_active_filter_with_no_match_keeps_reset_and_context() -> None:
    result = forecast_view(
        forecast_watch='warning',
        forecast_history_state='no_data',
        forecast_bucket_per_page='10',
    )
    assert result['rows'] == []
    assert result['pagination']['total_items'] == 0
    assert result['pagination']['per_page'] == 10
    assert result['query_params']['tab'] == 'buckets'
    assert result['query_params']['history_window'] == '30d'
    assert result['query_params']['system_id'] == '42'


def test_forecast_clear_filters_preserves_history_and_page_size() -> None:
    result = forecast_view(forecast_bucket_per_page='10')
    assert result['pagination']['total_items'] == 3
    assert result['pagination']['per_page'] == 10
    assert result['watch'] == result['history_state'] == 'all'
    assert result['search'] == ''
    assert result['query_params']['history_window'] == '30d'


def test_forecast_search_pagination_and_invalid_filter_values() -> None:
    result = forecast_view(
        forecast_q='baseline',
        forecast_watch='normal',
        forecast_history_state='invalid',
        forecast_bucket_page='99',
    )
    assert [row['name'] for row in result['rows']] == ['baseline-missing', 'baseline-partial']
    assert result['history_state'] == 'all'
    assert result['pagination']['page'] == 1
    assert result['query_params']['forecast_q'] == 'baseline'


CONSUMER_ROWS = [
    {
        'name': 'metrics-healthy',
        'usage_bytes': 120.0,
        'usage_source': 'Thanos Query',
        'quota_bytes': 1000.0,
        'quota_state': 'configured',
        'quota_utilization': 12.0,
        'request_rate': 0.0,
        'error_ratio': 0.0,
    },
    {
        'name': 'inventory-pressure',
        'usage_bytes': 90.0,
        'usage_source': 'Committed Snapshot',
        'quota_bytes': 100.0,
        'quota_state': 'configured',
        'quota_utilization': 90.0,
        'request_rate': None,
        'error_ratio': None,
    },
    {
        'name': 'metrics-critical',
        'usage_bytes': 96.0,
        'usage_source': 'Thanos Query',
        'quota_bytes': 100.0,
        'quota_state': 'configured',
        'quota_utilization': 96.0,
        'request_rate': 1.5,
        'error_ratio': 2.5,
    },
    {
        'name': 'no-quota',
        'usage_bytes': 0.0,
        'usage_source': 'Thanos Query',
        'quota_bytes': None,
        'quota_state': 'not_configured',
        'quota_utilization': None,
        'request_rate': None,
        'error_ratio': None,
    },
    {
        'name': 'unknown',
        'usage_bytes': None,
        'usage_source': 'Metric Not Scraped',
        'quota_bytes': None,
        'quota_state': 'not_collected',
        'quota_utilization': None,
        'request_rate': None,
        'error_ratio': None,
    },
]


def consumer_view(**query: str) -> dict:
    return build_bucket_table_view(
        CONSUMER_ROWS,
        query,
        page_key='top_consumers',
        system=_System(),
        time_range='12h',
    )


def test_consumer_usage_context_preserves_missing_and_inventory_boundaries() -> None:
    assert [row['name'] for row in consumer_view(bucket_usage_context='metrics')['rows']] == [
        'metrics-healthy',
        'metrics-critical',
        'no-quota',
    ]
    assert [row['name'] for row in consumer_view(bucket_usage_context='inventory')['rows']] == ['inventory-pressure']
    assert [row['name'] for row in consumer_view(bucket_usage_context='unavailable')['rows']] == ['unknown']


def test_consumer_quota_state_and_pressure_reuse_capacity_thresholds() -> None:
    assert [row['name'] for row in consumer_view(bucket_quota_pressure='within')['rows']] == ['metrics-healthy']
    assert [row['name'] for row in consumer_view(bucket_quota_pressure='warning')['rows']] == ['inventory-pressure']
    assert [row['name'] for row in consumer_view(bucket_quota_pressure='critical')['rows']] == ['metrics-critical']
    assert [row['name'] for row in consumer_view(bucket_quota_state='not_configured')['rows']] == ['no-quota']
    assert [row['name'] for row in consumer_view(bucket_quota_state='unknown')['rows']] == ['unknown']


def test_consumer_request_evidence_counts_zero_as_observed_not_missing() -> None:
    available = consumer_view(bucket_request_evidence='available')
    assert [row['name'] for row in available['rows']] == ['metrics-healthy', 'metrics-critical']
    assert available['rows'][0]['request_rate'] == 0.0
    missing = consumer_view(bucket_request_evidence='unavailable')
    assert [row['name'] for row in missing['rows']] == [
        'inventory-pressure',
        'no-quota',
        'unknown',
    ]
    assert all(row['request_rate'] is None for row in missing['rows'])


def test_consumer_combined_filter_respects_query_context_rows_and_empty_state() -> None:
    selected = consumer_view(
        bucket_q='critical',
        bucket_usage_context='metrics',
        bucket_quota_state='configured',
        bucket_quota_pressure='critical',
        bucket_request_evidence='available',
        bucket_per_page='10',
    )
    assert [row['name'] for row in selected['rows']] == ['metrics-critical']
    assert selected['pagination']['per_page'] == 10
    assert selected['query_params']['time_range'] == '12h'
    assert selected['query_params']['tab'] == 'records'
    assert selected['query_params']['bucket_request_evidence'] == 'available'
    assert selected['query_params']['bucket_quota_pressure'] == 'critical'
    empty = consumer_view(bucket_quota_state='not_configured', bucket_request_evidence='available')
    assert empty['rows'] == []
    assert empty['pagination']['total_items'] == 0


def test_consumer_clear_and_invalid_filters_preserve_scope() -> None:
    cleared = consumer_view(bucket_per_page='25')
    assert cleared['pagination']['total_items'] == 5
    assert cleared['pagination']['per_page'] == 25
    assert cleared['query_params']['tab'] == 'records'
    assert cleared['query_params']['system_id'] == '42'
    for key in ('usage_context', 'quota_state', 'quota_pressure', 'request_evidence'):
        assert cleared[key] == 'all'

    invalid = consumer_view(
        bucket_usage_context='invalid',
        bucket_quota_state='invalid',
        bucket_quota_pressure='invalid',
        bucket_request_evidence='invalid',
        bucket_page='999',
    )
    assert invalid['pagination']['page'] == 1
    assert invalid['pagination']['total_items'] == 5
    for key in ('usage_context', 'quota_state', 'quota_pressure', 'request_evidence'):
        assert invalid[key] == 'all'


def test_consumer_request_filter_does_not_leak_to_other_domains() -> None:
    result = build_bucket_table_view(
        CONSUMER_ROWS,
        {'bucket_request_evidence': 'available', 'bucket_quota_pressure': 'critical'},
        page_key='performance',
        system=_System(),
        time_range='6h',
    )
    assert len(result['rows']) == 5
    assert result['request_evidence'] == 'all'
    assert result['quota_pressure'] == 'all'
    assert 'bucket_request_evidence' not in result['query_params']
