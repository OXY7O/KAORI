from app.integrations.contracts import HealthFactor
from app.integrations.runtime.scoring import calculate_health


def test_runtime_health_is_healthy_when_weighted_factors_are_good():
    state = calculate_health((
        HealthFactor('connectivity', 'Connectivity', 'success', 40, 100),
        HealthFactor('api', 'API', 'success', 40, 95),
        HealthFactor('latency', 'Latency', 'success', 20, 90),
    ))
    assert state.status == 'healthy'
    assert state.score == 96


def test_runtime_health_is_unhealthy_when_critical_factor_fails():
    state = calculate_health((
        HealthFactor('connectivity', 'Connectivity', 'failed', 30, 0),
        HealthFactor('capability', 'Capability', 'success', 10, 100),
    ))
    assert state.status == 'unhealthy'
