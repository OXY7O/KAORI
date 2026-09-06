from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_kubernetes_analytics_hero_copy_follows_canonical_concise_operational_context() -> None:
    expected = {
        'app/templates/kubernetes/analytics/capacity/partials/_hero.html': 'Review worker headroom, scheduling pressure, and emerging capacity risks.',
        'app/templates/kubernetes/analytics/workload/partials/_hero.html': 'Review workload governance, utilization, QoS, and right-sizing evidence.',
        'app/templates/kubernetes/analytics/forecast/partials/_hero.html': 'Review projected demand, growth trends, thresholds, and capacity risk.',
        'app/templates/kubernetes/analytics/top_consumers/partials/_hero.html': 'Identify leading resource consumers, concentration, and operational pressure.',
        'app/templates/kubernetes/analytics/alerts/partials/_hero.html': 'Review active alerts, anomalies, routing context, ownership, readiness, and supporting operational evidence.',
    }

    for path, copy in expected.items():
        assert copy in read(path)


def test_minio_copy_is_balanced_between_registration_detail_and_boundary_density() -> None:
    index = read('app/templates/integrations/storage/object_storage/providers/minio/index.html')
    configuration = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_configuration.html'
    )
    validation = read(
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_validation.html'
    )

    assert (
        'Register, validate, govern, and maintain reusable MinIO connections together with their consumer bindings and lifecycle state.'
        in index
    )
    assert (
        'MinIO owns S3 storage state; observability sources stay independent. KAORI governs registration and asset-scoped binding evidence.'
        in index
    )
    assert (
        'MinIO owns S3 storage state; observability sources remain independent. KAORI correlates asset-scoped binding evidence without copying credentials.'
        in configuration
    )
    assert (
        'The secret key stays encrypted; registration and Full Validation use governed S3 discovery.' in configuration
    )
    assert (
        'Full Validation owns S3 capabilities; Runtime Refresh owns live health; Inventory Sync owns committed assets; bindings own consumer evidence.'
        in validation
    )


def test_metrics_source_validation_copy_keeps_provider_consumer_boundary_concise() -> None:
    validation = read(
        'app/templates/integrations/observability/metrics_source/partials/_detail_validation_content.html'
    )

    assert (
        'Core API evidence determines provider readiness; consumer capabilities stay outside this registry.'
        in validation
    )
    assert (
        'Validate provider compatibility and Prometheus HTTP API v1 / PromQL core. Consumer contracts stay in Bindings & Consumers.'
        in validation
    )


def test_superseded_copy_is_removed() -> None:
    paths = [
        'app/templates/kubernetes/analytics/capacity/partials/_hero.html',
        'app/templates/kubernetes/analytics/workload/partials/_hero.html',
        'app/templates/kubernetes/analytics/forecast/partials/_hero.html',
        'app/templates/kubernetes/analytics/top_consumers/partials/_hero.html',
        'app/templates/kubernetes/analytics/alerts/partials/_hero.html',
        'app/templates/integrations/storage/object_storage/providers/minio/index.html',
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_configuration.html',
        'app/templates/integrations/storage/object_storage/providers/minio/partials/_detail_validation.html',
        'app/templates/integrations/observability/metrics_source/partials/_detail_validation_content.html',
    ]
    combined = '\n'.join(read(path) for path in paths)

    superseded = [
        'Review worker headroom, allocation pressure, scheduling constraints, and emerging capacity risks across active workloads.',
        'Review quotas, requests, limits, QoS classes, utilization patterns, and right-sizing evidence across workloads.',
        'Review projected demand, threshold timing, growth trends, and potential future capacity risks across the cluster.',
        'Review the highest CPU, memory, pod, and PVC consumers to identify concentration and resource pressure.',
        'Review worker headroom, allocation pressure, and scheduling risk.',
        'Review quotas, requests, limits, QoS, and right-sizing evidence.',
        'Review projected demand, threshold timing, and future capacity risk.',
        'Review the highest CPU, memory, pod, and PVC consumers.',
        'Review active alerts, anomalies, routing, ownership, and readiness.',
        'Register, validate, and govern reusable MinIO connections and consumer bindings.',
        'MinIO owns storage state; observability sources stay independent. KAORI governs registration and binding evidence.',
        'MinIO owns S3 state; Metrics Source and Alertmanager remain independent observability sources. KAORI correlates binding evidence without copying their credentials into MinIO.',
        'The secret key remains encrypted; registration and Full Validation use governed S3 discovery.',
        'Full Validation owns capabilities, Runtime Refresh health, Inventory Sync assets; bindings own consumer evidence.',
        'Validate provider compatibility and the shared Prometheus HTTP API v1 / PromQL core. Consumer contracts stay in Bindings & Consumers.',
    ]

    for copy in superseded:
        assert copy not in combined
