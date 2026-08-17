from __future__ import annotations

from app.integrations.metrics.query_profiles.object_storage_audit import ObjectStorageMetricsProfileAuditor
from app.integrations.metrics.query_profiles.object_storage_v1 import list_object_storage_queries


def _series_rows(*, exclude: set[str] | None = None) -> list[dict[str, str]]:
    excluded = exclude or set()
    labels_by_metric: dict[str, set[str]] = {}
    for definition in list_object_storage_queries():
        for metric in definition.required_metrics:
            labels_by_metric.setdefault(metric, set())
        for metric, labels in definition.required_labels:
            labels_by_metric.setdefault(metric, set()).update(labels)
    rows: list[dict[str, str]] = []
    for metric, labels in labels_by_metric.items():
        if metric in excluded:
            continue
        row = {'__name__': metric, 'job': 'minio-production'}
        row.update({label: f'{label}-value' for label in labels})
        rows.append(row)
    return rows


class FakePrometheusHttpQueryClient:
    def __init__(self, *, series_rows: list[dict[str, str]], empty_expressions: set[str] | None = None) -> None:
        self.series_rows = series_rows
        self.empty_expressions = empty_expressions or set()
        self.series_calls = 0
        self.query_calls: list[str] = []

    def series(self, metrics: list[str], limit: int | None = None) -> dict:
        self.series_calls += 1
        assert metrics
        assert limit is None
        return {'status': 'success', 'data': self.series_rows}

    def query(self, expression: str) -> dict:
        self.query_calls.append(expression)
        result = [] if expression in self.empty_expressions else [{'metric': {}, 'value': [1, '1']}]
        return {'status': 'success', 'data': {'result': result}}


def test_readiness_audit_validates_metric_family_labels_and_registered_queries() -> None:
    client = FakePrometheusHttpQueryClient(series_rows=_series_rows())

    audit = ObjectStorageMetricsProfileAuditor(client).audit(execute_queries=True)

    assert audit['status'] == 'ready'
    assert audit['summary']['required_blocked'] == 0
    assert audit['summary']['required_no_data'] == 0
    assert audit['summary']['ready'] == audit['summary']['total']
    assert client.series_calls == 1
    assert len(client.query_calls) == len(list_object_storage_queries())


def test_optional_metric_family_gap_does_not_block_required_contract() -> None:
    client = FakePrometheusHttpQueryClient(series_rows=_series_rows(exclude={'minio_bucket_quota_total_bytes'}))

    audit = ObjectStorageMetricsProfileAuditor(client).audit(execute_queries=True)
    quota = next(item for item in audit['items'] if item['key'] == 'object_storage.bucket.quota')

    assert audit['status'] == 'ready'
    assert quota['tier'] == 'optional'
    assert quota['status'] == 'unsupported'
    assert audit['summary']['unsupported'] == 1
    assert audit['summary']['required_blocked'] == 0


def test_required_metric_family_gap_is_visible_as_partial_contract_evidence() -> None:
    client = FakePrometheusHttpQueryClient(series_rows=_series_rows(exclude={'minio_cluster_usage_total_bytes'}))

    audit = ObjectStorageMetricsProfileAuditor(client).audit(execute_queries=True)
    usage = next(item for item in audit['items'] if item['key'] == 'object_storage.usage.total_bytes')

    assert audit['status'] == 'partial'
    assert usage['tier'] == 'required'
    assert usage['status'] == 'blocked'
    assert audit['summary']['required_blocked'] == 1


def test_successful_query_without_samples_is_not_misreported_as_unsupported() -> None:
    request_query = next(
        definition.expression
        for definition in list_object_storage_queries()
        if definition.key == 'object_storage.requests.rate'
    )
    client = FakePrometheusHttpQueryClient(series_rows=_series_rows(), empty_expressions={request_query})

    audit = ObjectStorageMetricsProfileAuditor(client).audit(execute_queries=True)
    request_rate = next(item for item in audit['items'] if item['key'] == 'object_storage.requests.rate')

    assert audit['status'] == 'partial'
    assert request_rate['status'] == 'no_data'
    assert request_rate['missing_metrics'] == []
    assert request_rate['execution_state'] == 'no_data'
