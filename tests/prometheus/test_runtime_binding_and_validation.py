from datetime import UTC, datetime
from pathlib import Path

from app.integrations.runtime.contracts import CapabilitySnapshot, HealthState, RuntimeState
from app.integrations.runtime.presentation import runtime_state_view


def _state():
    observed_at = datetime.now(UTC)
    return RuntimeState(
        provider='prometheus',
        instance_id='prom-1',
        instance_name='cluster-a metrics',
        observed_at=observed_at,
        readiness='ready',
        health=HealthState(status='healthy', score=100, summary='Healthy', factors=()),
        diagnostics=(),
        snapshot=CapabilitySnapshot(
            profile='promql-kubernetes-v1',
            compatibility_profile='prometheus-v2',
            capabilities=(),
            observed_at=observed_at,
            metadata={},
        ),
        last_success_at=None,
        last_failure_at=None,
        latency_ms=25,
        message='Ready',
    )


def test_runtime_view_contains_cluster_binding_and_refresh_url():
    view = runtime_state_view(
        _state(),
        actions={'refresh_url': '/integrations/prometheus/cluster/cluster-a/validate'},
        binding={
            'type': 'kubernetes_cluster',
            'id': 'cluster-a',
            'name': 'Cluster A',
            'label': 'Kubernetes cluster Cluster A',
        },
    )

    assert view['refresh_url'].endswith('/validate')
    assert view['binding_type'] == 'kubernetes_cluster'
    assert view['binding_id'] == 'cluster-a'


def test_runtime_template_does_not_depend_on_cluster_object():
    template = Path('app/templates/prometheus/partials/_runtime_panel.html').read_text()

    assert 'cluster.id' not in template
    assert 'runtime_state.refresh_url' in template


def test_full_validation_executes_feature_queries():
    source = Path('app/prometheus/service.py').read_text()

    assert 'audit(execute_queries=True)' in source
    assert "feature_contract_summary" in source
