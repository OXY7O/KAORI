"""Strict read-only internal Secret Store health gate (#5202)."""

import pytest
import requests
from flask import Flask

from app.commands.secret_store import verify_secret_store


class _Response:
    is_redirect = False
    content = b'{}'

    def __init__(self, status, body):
        self.status_code = status
        self.body = body

    def json(self):
        return self.body


ACTIVE = {
    'initialized': True,
    'sealed': False,
    'standby': False,
    'version': '2.7.3',
}


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setenv('KAORI_INTERNAL_SECRET_STORE_PROVIDER', 'openbao')
    monkeypatch.setenv('KAORI_INTERNAL_SECRET_STORE_ENDPOINT', 'https://secret-store:8200')
    monkeypatch.setenv('INTEGRATION_OPENBAO_ALLOWED_ORIGINS', 'https://secret-store:8200,https://external.invalid:8200')
    monkeypatch.setenv('INTEGRATION_OPENBAO_CA_BUNDLE', '/trust/openbao.pem')
    app = Flask(__name__)
    app.cli.add_command(verify_secret_store)
    return app.test_cli_runner()


@pytest.mark.parametrize(
    ('code', 'overrides', 'success'),
    [
        (200, {}, True),
        (501, {'initialized': False, 'sealed': True}, False),
        (503, {'sealed': True}, False),
        (429, {'standby': True}, False),
        (200, {'sealed': 'false'}, False),
        (200, {'initialized': 1}, False),
        (200, {'standby': True}, False),
        (200, {'performance_standby': False}, True),
        (200, {'performance_standby': True}, False),
        (200, {'performance_standby': None}, False),
        (200, {'version': '2.7.2'}, False),
        (200, {'version': None}, False),
    ],
)
def test_verify_secret_store_strict_health(runner, monkeypatch, code, overrides, success):
    def request(session, method, url, **kwargs):
        assert method == 'GET'
        assert url == 'https://secret-store:8200/v1/sys/health'
        assert kwargs['headers'] == {'Accept': 'application/json'}
        assert kwargs['verify'] == '/trust/openbao.pem'
        assert kwargs['allow_redirects'] is False
        assert session.trust_env is False
        return _Response(code, {**ACTIVE, **overrides, 'unexpected': 'do-not-print'})

    monkeypatch.setattr(requests.Session, 'request', request)
    result = runner.invoke(args=['verify-secret-store'])
    assert (result.exit_code == 0) is success
    assert 'do-not-print' not in result.output
    assert ('health verification PASS' in result.output) is success


def test_verify_secret_store_missing_fields(runner, monkeypatch):
    monkeypatch.setattr(requests.Session, 'request', lambda *args, **kwargs: _Response(200, {}))
    assert runner.invoke(args=['verify-secret-store']).exit_code != 0


@pytest.mark.parametrize(
    ('key', 'value'),
    [
        ('KAORI_INTERNAL_SECRET_STORE_PROVIDER', 'vault'),
        ('KAORI_INTERNAL_SECRET_STORE_ENDPOINT', 'https://external.invalid:8200'),
        ('INTEGRATION_OPENBAO_CA_BUNDLE', ''),
        ('INTEGRATION_OPENBAO_ALLOWED_ORIGINS', 'https://external.invalid:8200'),
    ],
)
def test_verify_secret_store_requires_internal_trust(runner, monkeypatch, key, value):
    monkeypatch.setenv(key, value)

    def no_request(*args, **kwargs):
        pytest.fail('Unapproved network request')

    monkeypatch.setattr(requests.Session, 'request', no_request)
    assert runner.invoke(args=['verify-secret-store']).exit_code != 0
