from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.kubernetes.operations.configmaps import runtime


def test_configmap_runtime_delegates_client_creation_to_registered_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The provider adapter owns per-request TLS policy; ConfigMap never changes global TLS."""
    events: list[object] = []
    cluster = SimpleNamespace(id='cluster-a')
    connection = object()
    api = object()

    def resolve(selected):
        events.append(('resolve', selected.id))
        return connection

    def registry(capability):
        assert capability == 'container_orchestrator'

        def execute(operation, resolved_connection):
            events.append(('execute', operation, resolved_connection is connection))
            return SimpleNamespace(core_api=lambda: api)

        return SimpleNamespace(execute=execute)

    monkeypatch.setattr(runtime, 'connection_for_cluster', resolve)
    monkeypatch.setattr(runtime, 'get_integration', registry)

    def callback(selected_api):
        events.append(('callback', selected_api is api))
        return 'ok'

    assert runtime.live_call(cluster, 'integration test', callback) == 'ok'
    assert events == [
        ('resolve', 'cluster-a'),
        ('execute', 'client.build', True),
        ('callback', True),
    ]


def test_secret_reveal_lock_query_targets_only_request_table() -> None:
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.orm import Session

    from app.models import SecretRevealRequest

    session = Session()
    try:
        statement = (
            session.query(SecretRevealRequest)
            .filter_by(id='request-id')
            .enable_eagerloads(False)
            .with_for_update(of=SecretRevealRequest)
            .statement
        )
        compiled = str(statement.compile(dialect=postgresql.dialect()))
    finally:
        session.close()

    assert 'LEFT OUTER JOIN' not in compiled
    assert 'FOR UPDATE OF secret_reveal_requests' in compiled
