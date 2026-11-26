"""Read-only post-unseal bootstrap inspection (#5202)."""

import pytest
import requests
from flask import Flask

from app.commands.secret_store import bootstrap_secret_store


class _Response:
    is_redirect = False
    content = b'{}'

    def __init__(self, status, body):
        self.status_code = status
        self.body = body

    def json(self):
        return self.body


@pytest.fixture
def runner(monkeypatch):
    endpoint = 'https://secret-store:8200'
    monkeypatch.setenv('KAORI_INTERNAL_SECRET_STORE_PROVIDER', 'openbao')
    monkeypatch.setenv('KAORI_INTERNAL_SECRET_STORE_ENDPOINT', endpoint)
    monkeypatch.setenv('INTEGRATION_OPENBAO_ALLOWED_ORIGINS', endpoint)
    monkeypatch.setenv('INTEGRATION_OPENBAO_CA_BUNDLE', '/trust/openbao.pem')
    app = Flask(__name__)
    app.cli.add_command(bootstrap_secret_store)
    return app.test_cli_runner()


@pytest.mark.parametrize('failure', ['', 'sealed', 'root', 'ttl', 'audit', 'raw', 'denied', 'malformed'])
def test_bootstrap_plan_read_only(runner, monkeypatch, failure):
    calls = []
    fixture = 'fixture'

    def request(session, method, url, **kwargs):
        assert method == 'GET'
        assert session.trust_env is False
        assert kwargs['allow_redirects'] is False
        assert kwargs['verify'] == '/trust/openbao.pem'
        path = url.split('/v1/', 1)[1]
        calls.append(path)
        if path == 'sys/health':
            assert 'X-Vault-Token' not in kwargs['headers']
            return _Response(
                503 if failure == 'sealed' else 200,
                {'initialized': True, 'sealed': failure == 'sealed', 'standby': False, 'version': '2.7.3'},
            )
        assert kwargs['headers']['X-Vault-Token'] == fixture
        if path == 'auth/token/lookup-self':
            policy = 'root' if failure == 'root' else 'inspect'
            ttl = 0 if failure == 'ttl' else 60
            return _Response(200, {'data': {'policies': [policy], 'ttl': ttl}})
        if path == 'sys/audit':
            audit = {
                'kaori-operator/': {
                    'type': 'file',
                    'options': {
                        'file_path': '/openbao/audit/audit.jsonl',
                        'log_raw': 'true' if failure == 'raw' else 'false',
                    },
                },
            }
            return _Response(200, {'data': {} if failure == 'audit' else audit})
        if path == 'sys/mounts':
            return _Response(
                403 if failure == 'denied' else 200,
                {'data': {'hidden-name/': {'type': 'kv', 'options': {'version': '2'}}}},
            )
        if path == 'sys/auth':
            return _Response(200, {'data': {'hidden-auth/': None if failure == 'malformed' else {'type': 'approle'}}})
        pytest.fail('Unexpected provider call')

    monkeypatch.setattr(requests.Session, 'request', request)
    result = runner.invoke(args=['bootstrap-secret-store', '--plan'], input=fixture + '\n')
    assert (result.exit_code == 0) is (not failure)
    assert fixture not in result.output
    assert 'hidden-name' not in result.output and 'hidden-auth' not in result.output
    if not failure:
        assert 'KV v2 mounts=1, AppRole mounts=1' in result.output
        assert 'PLAN ONLY' in result.output
    if failure in {'root', 'ttl'}:
        assert calls[-1] == 'auth/token/lookup-self'
    if failure == 'sealed':
        assert calls == ['sys/health']


def test_bootstrap_apply_unavailable(runner, monkeypatch):
    def no_request(*args, **kwargs):
        pytest.fail('Apply must not contact provider')

    monkeypatch.setattr(requests.Session, 'request', no_request)
    result = runner.invoke(args=['bootstrap-secret-store'])
    assert result.exit_code != 0
    assert 'Only --plan' in result.output
