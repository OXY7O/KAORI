from types import SimpleNamespace

from app.analytics.utilization.service import UtilizationService


class FakeConsumer:
    def __init__(self):
        self.calls = []

    def query(self, promql, *, required_capabilities):
        self.calls.append((promql, required_capabilities))
        return {'data': {'result': [{'value': [0, '25']}]}}

    def requirements(self, required_capabilities):
        return SimpleNamespace(ok=True, payload={'missing_capabilities': []})


class FakePrometheus:
    def __init__(self):
        self.consumer = FakeConsumer()


def test_utilization_requires_complete_contract():
    assert UtilizationService.REQUIRED_CAPABILITIES == (
        'instant_query',
        'range_query',
        'kubernetes_identity',
        'utilization_metrics',
        'node_filesystem_identity',
    )


def test_utilization_storage_node_query_uses_canonical_node_identity():
    prometheus = FakePrometheus()
    service = UtilizationService(prometheus)

    value = service.get_storage_capacity('worker-a')

    assert value == 25.0
    query, capabilities = prometheus.consumer.calls[-1]
    assert 'node="worker-a"' in query
    assert 'instance=' not in query
    assert capabilities == UtilizationService.REQUIRED_CAPABILITIES
