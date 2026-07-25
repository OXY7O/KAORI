from __future__ import annotations

from types import SimpleNamespace

from app.analytics.materialization import requests as materialization_requests
from app.analytics.materialization.requests import MaterializedRequest
from app.analytics.materialization.serialization import ClusterReference
from app.analytics.materialization.service import SnapshotResult


def _cluster(cluster_id: str = 'cluster-b') -> ClusterReference:
    return ClusterReference(
        id=cluster_id,
        name='Cluster B',
        environment='development',
        status='connected',
    )


def test_materialized_request_contract_exposes_dependency_blocker() -> None:
    request_state = MaterializedRequest(
        result=SnapshotResult(None, None, 'missing', False),
        cluster=_cluster(),
        parameters={'cluster_id': 'cluster-b'},
        dispatched=False,
    )

    assert request_state.dependency_blocker is None


def test_dependency_blocker_prevents_background_dispatch(monkeypatch) -> None:
    blocker = {
        'kind': 'prometheus_capability',
        'stage': 2,
        'badge': 'Forecast Capability Incomplete',
        'title': 'Forecast Integration Contract Not Ready',
        'description': 'Capability evidence is incomplete.',
        'diagnostic_detail': None,
        'icon': 'shield-alert',
        'action_label': 'Review Capability',
        'action_url': '/integrations/prometheus',
        'permission': 'settings.manage_integrations',
    }

    monkeypatch.setattr(
        materialization_requests,
        'canonical_parameters',
        lambda _dataset_key, _parameters: {'history_window': '30d'},
    )
    monkeypatch.setattr(
        materialization_requests,
        'selected_cluster_from_request',
        lambda **_kwargs: _cluster(),
    )
    monkeypatch.setattr(
        materialization_requests,
        'read_snapshot',
        lambda **_kwargs: SnapshotResult(None, None, 'missing', False),
    )
    monkeypatch.setattr(
        materialization_requests,
        '_dependency_blocker',
        lambda **_kwargs: blocker,
    )

    def unexpected_dispatch(**_kwargs):
        raise AssertionError('blocked analytics requests must not dispatch a job')

    monkeypatch.setattr(
        materialization_requests,
        'dispatch_registered_job',
        unexpected_dispatch,
    )

    resolved = materialization_requests.resolve_materialized_request(
        dataset_key='analytics.forecast',
        job_key='analytics.forecast.materialize',
        parameters={'history_window': '30d'},
    )

    assert resolved.cluster == _cluster()
    assert resolved.dispatched is False
    assert resolved.dependency_blocker == blocker


def test_ready_request_preserves_canonical_snapshot_parameters(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        materialization_requests,
        'canonical_parameters',
        lambda _dataset_key, _parameters: {'history_window': '30d'},
    )
    monkeypatch.setattr(
        materialization_requests,
        'selected_cluster_from_request',
        lambda **_kwargs: _cluster(),
    )

    def read_snapshot(**kwargs):
        captured.update(kwargs)
        return SnapshotResult({'cluster': _cluster()}, None, 'fresh', False)

    monkeypatch.setattr(materialization_requests, 'read_snapshot', read_snapshot)
    monkeypatch.setattr(
        materialization_requests,
        '_dependency_blocker',
        lambda **_kwargs: None,
    )

    resolved = materialization_requests.resolve_materialized_request(
        dataset_key='analytics.forecast',
        job_key='analytics.forecast.materialize',
        parameters={
            'history_window': '30d',
            'forecast_horizon': '365d',
            'resource': 'memory',
        },
    )

    assert captured['parameters'] == {
        'history_window': '30d',
        'cluster_id': 'cluster-b',
    }
    assert resolved.dependency_blocker is None
    assert resolved.dispatched is False
