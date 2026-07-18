from app.analytics.capacity.service import CapacityService


def test_capacity_requires_complete_metrics_contract():
    assert CapacityService.REQUIRED_CAPABILITIES == (
        'instant_query',
        'range_query',
        'kubernetes_identity',
        'capacity_metrics',
        'resource_requests_limits',
    )
