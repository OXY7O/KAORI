"""Fail closed when fallback HTTP reachability is not positive health evidence."""

from types import SimpleNamespace

import pytest
import requests

from app.integrations.storage.object_storage.providers.minio import runtime
from app.integrations.storage.object_storage.providers.minio.contracts import MinioConnectionError


@pytest.mark.parametrize('status', [301, 302, 400, 401, 403, 404, 429, 500, 503])
def test_unqualified_fallback_head_rejects_non_success_status(monkeypatch, status: int) -> None:
    calls: list[tuple[str, str]] = []

    def respond(method, url, **kwargs):
        calls.append((method, url))
        assert kwargs['allow_redirects'] is False
        return SimpleNamespace(status_code=status)

    monkeypatch.setattr(runtime.requests, 'request', respond)
    with pytest.raises(MinioConnectionError, match=f'HTTP {status}'):
        runtime.probe_runtime_values(endpoint='https://s3.example.invalid', product='s3_compatible')
    assert calls == [('HEAD', 'https://s3.example.invalid/')]


@pytest.mark.parametrize('status', [200, 204])
def test_unqualified_fallback_head_accepts_only_2xx(monkeypatch, status: int) -> None:
    monkeypatch.setattr(runtime.requests, 'request', lambda *_args, **_kwargs: SimpleNamespace(status_code=status))
    result = runtime.probe_runtime_values(endpoint='https://s3.example.invalid', product='s3_compatible')
    assert result.connected is True
    assert result.status_code == status
    assert result.probe == 'endpoint-head'


@pytest.mark.parametrize('status', [200, 204, 401, 503])
def test_minio_uses_strict_liveness_get_status(monkeypatch, status: int) -> None:
    def respond(method, url, **_kwargs):
        assert method == 'GET'
        assert url == 'https://s3.example.invalid/minio/health/live'
        return SimpleNamespace(status_code=status)

    monkeypatch.setattr(runtime.requests, 'request', respond)
    if status == 200:
        assert runtime.probe_runtime_values(endpoint='https://s3.example.invalid', product='minio').connected
    else:
        with pytest.raises(MinioConnectionError, match=f'HTTP {status}'):
            runtime.probe_runtime_values(endpoint='https://s3.example.invalid', product='minio')


def test_fallback_timeout_never_produces_connected_state(monkeypatch) -> None:
    def timeout(*_args, **_kwargs):
        raise requests.exceptions.Timeout('timeout')

    monkeypatch.setattr(runtime.requests, 'request', timeout)
    with pytest.raises(MinioConnectionError, match='could not reach'):
        runtime.probe_runtime_values(endpoint='https://s3.example.invalid', product='s3_compatible')
