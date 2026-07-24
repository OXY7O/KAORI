from __future__ import annotations

from app.analytics.top_consumers.service import (
    format_bytes,
    get_resource_recommendation,
    get_selected_focus,
    get_selected_resource,
    get_selected_sort,
    get_selected_top_consumers_time_range,
    get_usage_percent,
    get_usage_risk,
    render_namespace_query,
)


def test_top_consumer_filters_reject_unknown_query_values() -> None:
    query_args = {
        'resource': 'unknown',
        'sort': 'unknown',
        'time_range': 'unknown',
        'focus': 'unknown',
    }

    assert get_selected_resource(query_args) == 'all'
    assert get_selected_sort(query_args) == 'usage_percent'
    assert get_selected_top_consumers_time_range(query_args) == '24h'
    assert get_selected_focus(query_args) == ''


def test_top_consumer_usage_prefers_limits_then_requests() -> None:
    assert get_usage_percent(usage=90, request=50, limit=100) == 90.0
    assert get_usage_percent(usage=45, request=50, limit=0) == 90.0
    assert get_usage_percent(usage=45, request=0, limit=0) == 0.0

    assert get_usage_risk(89.9)['key'] == 'warning'
    assert get_usage_risk(90.0)['key'] == 'critical'
    assert get_usage_risk(74.9)['key'] == 'normal'


def test_top_consumer_recommendations_preserve_resource_guardrails() -> None:
    assert (
        get_resource_recommendation(
            resource_type='cpu',
            usage_percent=50,
            request=0,
            limit=1,
        )
        == 'Add CPU request'
    )
    assert (
        get_resource_recommendation(
            resource_type='memory',
            usage_percent=95,
            request=1,
            limit=2,
        )
        == 'Increase memory limit'
    )
    assert (
        get_resource_recommendation(
            resource_type='pvc',
            usage_percent=75,
            request=0,
            limit=0,
        )
        == 'Expand PVC capacity'
    )


def test_top_consumer_query_escaping_and_byte_formatting_are_stable() -> None:
    query = render_namespace_query(
        namespace='team\\"platform',
        all_query='all',
        namespace_query='metric{namespace="$namespace"}',
    )

    assert query == 'metric{namespace="team\\\\\\"platform"}'
    assert format_bytes(0) == '0 B'
    assert format_bytes(1024) == '1.00 KiB'
    assert format_bytes(1024**3) == '1.00 GiB'
