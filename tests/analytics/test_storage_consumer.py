from types import SimpleNamespace

from app.analytics.storage.service import StorageAnalysisService
from app.prometheus.consumer import PrometheusConsumer


class FakeConsumer:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def query(self, promql, *, required_capabilities):
        self.calls.append((promql, required_capabilities))
        return self.payload


def _sample(metric, value):
    return {'metric': metric, 'value': [0, str(value)]}


def test_storage_filesystem_uses_canonical_identity_and_ignores_instance_only():
    consumer = FakeConsumer(
        {
            'data': {
                'result': [
                    _sample({'node': 'worker-a', 'device': '/dev/sda'}, 10),
                    _sample({'node': 'worker-a', 'device': '/dev/sdb'}, 5),
                    _sample({'nodename': 'worker-b'}, 7),
                    _sample({'instance': '10.0.0.4:9100'}, 99),
                ]
            }
        }
    )
    service = StorageAnalysisService(SimpleNamespace(), consumer)

    values = service.get_filesystem_vector_map('filesystem query')

    assert values == {'worker-a': 15.0, 'worker-b': 7.0}
    assert consumer.calls == [
        ('filesystem query', StorageAnalysisService.REQUIRED_CAPABILITIES)
    ]


def test_prometheus_requirements_reports_storage_capability_gap():
    consumer = PrometheusConsumer.__new__(PrometheusConsumer)
    consumer.cluster = SimpleNamespace(name='Production')
    consumer.config = SimpleNamespace(
        id=7,
        endpoint='https://thanos.example.test',
        endpoint_product='thanos',
        compatibility_profile='thanos-query-v0-39',
        capability_profile='prometheus-v2-kubernetes-v1',
        readiness_status='degraded',
        last_status='degraded',
        validation_message='Storage capability remediation is required.',
        capabilities={
            'available': ['instant_query', 'kubernetes_identity', 'pvc_usage'],
            'assessments': [
                {'key': 'node_filesystem_identity', 'status': 'misconfigured'},
            ],
        },
    )

    result = consumer.requirements(StorageAnalysisService.REQUIRED_CAPABILITIES)

    assert result.ok is False
    assert result.payload['missing_capabilities'] == ['node_filesystem_identity']
    assert result.diagnostics[-1].code == 'capability_requirements_not_satisfied'
