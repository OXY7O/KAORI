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
