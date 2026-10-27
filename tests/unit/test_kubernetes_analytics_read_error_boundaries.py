"""Read-only analytics availability degrades only on expected resolver failures."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace

import pytest
from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from app.integrations.observability.metrics_source.application import resolver as metrics_resolver
from app.kubernetes.analytics.materialization import requests as materialized_requests
from app.kubernetes.analytics.materialization.keys import CAPACITY_DATASET_KEY
from app.kubernetes.analytics.materialization.serialization import ClusterReference
from app.kubernetes.analytics.materialization.service import SnapshotResult
from app.kubernetes.analytics.overview import service as overview_service


def _cluster() -> ClusterReference:
    return ClusterReference(id='17', name='Review Cluster', environment='test')


def _raises(error: Exception) -> Callable[..., None]:
    def unavailable(*_args: object, **_kwargs: object) -> None:
        raise error

    return unavailable


@pytest.mark.parametrize(
    'error',
    [
        SQLAlchemyError('canonical database read failed'),
        RuntimeError('missing app context'),
        TypeError('invalid source snapshot type'),
        ValueError('invalid source snapshot value'),
    ],
)
def test_expected_source_read_failure_reports_not_ready(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    monkeypatch.setattr(materialized_requests, '_metrics_source_resolution', _raises(error))

    with Flask(__name__).app_context():
        result = materialized_requests._dataset_source_is_ready(
            dataset_key=CAPACITY_DATASET_KEY, cluster=_cluster(), parameters={}
        )

    assert result is False


def test_unexpected_source_read_defect_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        materialized_requests, '_metrics_source_resolution', _raises(LookupError('unexpected defect'))
    )

    with Flask(__name__).app_context():
        with pytest.raises(LookupError, match='unexpected defect'):
            materialized_requests._dataset_source_is_ready(
                dataset_key=CAPACITY_DATASET_KEY, cluster=_cluster(), parameters={}
            )


def test_selected_committed_source_keeps_dataset_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        materialized_requests,
        '_metrics_source_resolution',
        lambda **_kwargs: SimpleNamespace(selected=object()),
    )

    assert materialized_requests._dataset_source_is_ready(
        dataset_key=CAPACITY_DATASET_KEY, cluster=_cluster(), parameters={}
    ) is True


def _stub_materialized_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(materialized_requests, 'selected_cluster_from_request', lambda **_kwargs: _cluster())
    monkeypatch.setattr(
        materialized_requests, 'read_snapshot', lambda **_kwargs: SnapshotResult(None, None, 'missing', False)
    )
    monkeypatch.setattr(
        materialized_requests,
        'metrics_source_connection_blocker',
        lambda _cluster, **_kwargs: {'kind': 'metrics_source_connection'},
    )


@pytest.mark.parametrize(
    'error',
    [
        SQLAlchemyError('canonical database read failed'),
        RuntimeError('missing app context'),
        TypeError('invalid dependency type'),
        ValueError('invalid dependency value'),
    ],
)
def test_expected_dependency_read_error_keeps_dispatch_blocked(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    _stub_materialized_request(monkeypatch)
    monkeypatch.setattr(materialized_requests, '_dependency_state', _raises(error))

    with Flask(__name__).app_context():
        outcome = materialized_requests.resolve_materialized_request(
            dataset_key=CAPACITY_DATASET_KEY, job_key='capacity', parameters={}
        )

    assert outcome.dispatched is False
    assert outcome.dependency_blocker is not None
    assert outcome.dependency_blocker['kind'] == 'metrics_source_connection'


def test_unexpected_dependency_defect_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_materialized_request(monkeypatch)
    monkeypatch.setattr(materialized_requests, '_dependency_state', _raises(LookupError('unexpected defect')))

    with Flask(__name__).app_context():
        with pytest.raises(LookupError, match='unexpected defect'):
            materialized_requests.resolve_materialized_request(
                dataset_key=CAPACITY_DATASET_KEY, job_key='capacity', parameters={}
            )


@pytest.mark.parametrize('error', [SQLAlchemyError('DB down'), RuntimeError('context missing')])
def test_expected_overview_metrics_lookup_error_uses_first_cluster(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    monkeypatch.setattr(
        overview_service, 'db', SimpleNamespace(session=SimpleNamespace(scalars=lambda _stmt: SimpleNamespace(all=lambda: [])))
    )
    monkeypatch.setattr(metrics_resolver, 'resolve_metrics_sources', _raises(error))
    clusters = [{'id': '17'}, {'id': '18'}]

    assert overview_service._resolve_selected_cluster(clusters=clusters, selected_cluster_id=None) == clusters[0]


def test_unexpected_overview_metrics_lookup_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        overview_service, 'db', SimpleNamespace(session=SimpleNamespace(scalars=lambda _stmt: SimpleNamespace(all=lambda: [])))
    )
    monkeypatch.setattr(metrics_resolver, 'resolve_metrics_sources', _raises(LookupError('unexpected defect')))

    with pytest.raises(LookupError, match='unexpected defect'):
        overview_service._resolve_selected_cluster(clusters=[{'id': '17'}], selected_cluster_id=None)


def test_expected_optional_presenter_import_error_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(overview_service, '__import__', _raises(ImportError('optional module absent')), raising=False)

    with Flask(__name__).app_context():
        assert overview_service._call_optional_snapshot(module_path='missing.optional', function_names=['snapshot']) is None


def test_unexpected_presenter_initialization_defect_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(overview_service, '__import__', _raises(RuntimeError('unexpected import bug')), raising=False)

    with pytest.raises(RuntimeError, match='unexpected import bug'):
        overview_service._call_optional_snapshot(module_path='broken.optional', function_names=['snapshot'])
