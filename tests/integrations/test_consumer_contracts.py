from types import SimpleNamespace

import pytest

from app.integrations.consumer import ConsumerDiagnostic, ConsumerResult, ConsumerSource
from app.prometheus.consumer import PrometheusConsumer
from app.prometheus.exceptions import PrometheusError


def test_consumer_result_exposes_safe_canonical_shape():
    result = ConsumerResult(
        ok=False,
        payload={},
        source=ConsumerSource(
            provider='prometheus',
            instance_id=1,
            instance_name='Production metrics',
            endpoint_product='thanos',
            readiness='degraded',
        ),
        diagnostics=(
            ConsumerDiagnostic(
                code='missing_capability',
                message='Storage node identity is unavailable.',
                remediation='Add a canonical node label.',
                source_owner='Prometheus metrics pipeline',
                detail='instance=10.0.0.1:9100',
            ),
        ),
        required_capabilities=('node_filesystem_identity',),
    )

    payload = result.to_dict()
    assert payload['ok'] is False
    assert payload['source']['endpoint_product'] == 'thanos'
    assert payload['required_capabilities'] == ['node_filesystem_identity']
    assert payload['error'] == 'Storage node identity is unavailable.'


def test_prometheus_consumer_rejects_confirmed_missing_capability():
    consumer = PrometheusConsumer.__new__(PrometheusConsumer)
    consumer.config = SimpleNamespace(
        readiness_status='ready',
        validation_message=None,
        capabilities={
            'available': ['instant_query'],
            'assessments': [
                {'key': 'node_filesystem_identity', 'status': 'misconfigured'},
            ],
        },
    )

    with pytest.raises(PrometheusError, match='node_filesystem_identity'):
        consumer._require_capabilities(('node_filesystem_identity',))


def test_prometheus_consumer_keeps_migrated_snapshot_compatible():
    consumer = PrometheusConsumer.__new__(PrometheusConsumer)
    consumer.config = SimpleNamespace(
        readiness_status='ready',
        validation_message=None,
        capabilities=None,
    )

    consumer._require_capabilities(('instant_query',))
