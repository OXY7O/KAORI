from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.kubernetes_operations.configmaps import runtime


@contextmanager
def _tls_context(*, enabled: bool):
    yield enabled


def test_configmap_runtime_wraps_registered_client_with_cluster_tls_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[object] = []
    cluster = SimpleNamespace(id='cluster-a')
    api = object()

    monkeypatch.setattr(runtime, 'tls_policy_for_cluster', lambda selected: ('verify', True))
    monkeypatch.setattr(runtime, 'weak_tls_context', _tls_context)

    def factory(selected):
        events.append(('factory', selected.id))
        return api

    def callback(selected_api):
        events.append(('callback', selected_api is api))
        return 'ok'

    assert runtime._call(cluster, 'integration test', factory, callback) == 'ok'
    assert events == [('factory', 'cluster-a'), ('callback', True)]
