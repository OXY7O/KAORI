from __future__ import annotations

from types import SimpleNamespace

from app.analytics.kubernetes import job_adapter
from app.analytics.kubernetes.materialization.catalog import (
    source_binding_capabilities,
    source_technical_capabilities,
)


def test_domain_readiness_is_advisory_to_worker_execution_contract() -> None:
    assert source_binding_capabilities('analytics.workload') == ('metrics',)
    assert source_technical_capabilities('analytics.workload') == (
        'instant_query',
        'range_query',
    )
    assert source_binding_capabilities('analytics.storage') == ('metrics',)
    assert source_technical_capabilities('analytics.storage') == ('instant_query',)


def test_on_demand_request_only_attaches_to_matching_fleet_work_item() -> None:
    job = SimpleNamespace(
        payload_json={
            'work_items': [
                {
                    'cluster_id': 'cluster-a',
                    'dataset_key': 'analytics.workload',
                    'parameters': {
                        'cluster_id': 'cluster-a',
                        'time_range': '24h',
                    },
                }
            ]
        }
    )

    assert job_adapter._job_contains_requested_work_item(
        job,
        {
            'cluster_id': 'cluster-a',
            'dataset_key': 'analytics.workload',
            'snapshot_parameters': {
                'cluster_id': 'cluster-a',
                'time_range': '24h',
            },
        },
    )
    assert not job_adapter._job_contains_requested_work_item(
        job,
        {
            'cluster_id': 'cluster-b',
            'dataset_key': 'analytics.workload',
            'snapshot_parameters': {
                'cluster_id': 'cluster-b',
                'time_range': '24h',
            },
        },
    )
    assert not job_adapter._job_contains_requested_work_item(
        job,
        {
            'cluster_id': 'cluster-a',
            'dataset_key': 'analytics.workload',
            'snapshot_parameters': {
                'cluster_id': 'cluster-a',
                'time_range': '7d',
            },
        },
    )


def test_prometheus_consumer_reduces_domain_capabilities_to_query_transport() -> None:
    from app.prometheus.consumer import PrometheusConsumer

    assert PrometheusConsumer._execution_capabilities(
        (
            'instant_query',
            'range_query',
            'kubernetes_identity',
            'workload_metrics',
            'resource_requests_limits',
        )
    ) == ('instant_query', 'range_query')


def test_non_live_context_still_returns_utilization_service(monkeypatch) -> None:
    from app.analytics.kubernetes.common import context as analytics_context

    cluster = SimpleNamespace(
        id='cluster-b',
        name='Cluster B',
        created_at=None,
        environment='development',
        status='connected',
    )

    class ClusterQuery:
        def order_by(self, *_args):
            return self

        def all(self):
            return [cluster]

    selected_source = SimpleNamespace(
        operational_state='healthy',
        instance=SimpleNamespace(
            last_status='connected',
            last_response_time_ms=12,
            last_error=None,
            last_checked_at=None,
        ),
    )
    resolution = SimpleNamespace(selected=selected_source, candidates=(selected_source,))
    utilization_marker = object()

    ordered_field = SimpleNamespace(asc=lambda: object())
    monkeypatch.setattr(
        analytics_context,
        'Cluster',
        SimpleNamespace(query=ClusterQuery(), created_at=ordered_field, id=ordered_field),
    )
    monkeypatch.setattr(
        analytics_context,
        'get_selected_cluster',
        lambda **_kwargs: cluster,
    )
    monkeypatch.setattr(
        analytics_context,
        'resolve_instance_for_cluster',
        lambda _cluster_id: SimpleNamespace(endpoint='http://prometheus:9090'),
    )
    monkeypatch.setattr(
        analytics_context,
        'resolve_prometheus_sources',
        lambda **_kwargs: resolution,
    )
    monkeypatch.setattr(
        analytics_context,
        'PrometheusService',
        lambda _cluster: SimpleNamespace(),
    )
    monkeypatch.setattr(
        analytics_context,
        'UtilizationService',
        lambda _prometheus: utilization_marker,
    )

    _clusters, selected_cluster, utilization, payload = analytics_context.build_analysis_utilization_context(
        {'cluster_id': 'cluster-b', 'time_range': '24h'},
        check_prometheus_connection=False,
    )

    assert selected_cluster is cluster
    assert utilization is utilization_marker
    assert payload['dependency_blocker'] is None
    assert payload['prometheus_connected'] is True


def test_explicit_analytics_query_timeout_can_exceed_instance_default() -> None:
    from app.integrations.prometheus.client import PrometheusClient

    client = object.__new__(PrometheusClient)
    client.request_timeout_seconds = 300
    client.config = SimpleNamespace(timeout=5)

    assert client._request_timeout() == (5, 300)
