from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.reports.catalog import ReportContractError
from app.reports.storage.naming import build_report_object_key


def _report(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        'id': 71,
        'report_domain': 'kubernetes',
        'source_kind': 'kubernetes',
        'report_type': 'analytics_overview',
        'cluster_id': 'cluster-1',
        'cluster': SimpleNamespace(name='K8s PGN Staging'),
        'namespace': None,
        'period': '24h',
        'output_format': 'csv',
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_storage_key_contains_selected_cluster_report_type_and_format() -> None:
    key = build_report_object_key(
        _report(),
        generated_at=datetime(2026, 8, 3, 16, 0, tzinfo=UTC),
    )

    assert key.startswith('reports/kubernetes/kubernetes/2026/08/k8s-pgn-staging/analytics-overview/')
    assert '-k8s-pgn-staging-all-namespaces-last-24-hours-' in key
    assert key.endswith('.csv')


def test_storage_key_rejects_unscoped_report() -> None:
    with pytest.raises(ReportContractError, match='selected Kubernetes cluster'):
        build_report_object_key(_report(cluster_id=None, cluster=None))
