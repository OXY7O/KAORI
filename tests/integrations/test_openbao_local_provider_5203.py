"""Local OpenBao registry and runtime boundaries (#5203)."""

from dataclasses import replace

import pytest
from flask import Flask

from app.integrations.secrets_management.secrets_pki.providers.openbao import service
from app.integrations.secrets_management.secrets_pki.providers.openbao.adapter import runtime_adapter
from app.models.integration import IntegrationInstance
from app.models.openbao import OpenBaoInstance

_VALUES = service.OpenBaoConnectionInput(
    'Fixture Bao', 'external', 'https://bao.example.invalid:8200',
    '4f6db34e-2042-4f0c-a385-a0d39582acb8', 'approle', 'fixture-role', 'fixture-secret'
)


@pytest.fixture
def local_context(monkeypatch):
    app = Flask(__name__)
    app.config['APP_ENV'] = 'development'
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('INTEGRATION_OPENBAO_ALLOWED_ORIGINS', _VALUES.endpoint)
    monkeypatch.setenv('INTEGRATION_OPENBAO_CA_BUNDLE', '/fixture/ca.pem')
    with app.app_context():
        yield app


def test_local_provider_rejects_non_development_config(local_context):
    local_context.config['APP_ENV'] = 'production'
    assert not service.local_provider_enabled()
    with pytest.raises(ValueError):
        service._require_connection(_VALUES)


@pytest.mark.parametrize('values', [
    replace(_VALUES, ownership='internal'),
    replace(_VALUES, endpoint='https://secret-store:8200'),
    replace(_VALUES, cluster_id='not-a-cluster'),
    replace(_VALUES, auth_mount='approle/'),
])
def test_local_provider_rejects_invalid_target(local_context, values):
    with pytest.raises(ValueError):
        service._require_connection(values)


def test_separate_openbao_transport_and_token_never_returned(local_context, monkeypatch):
    calls = []

    class Client:
        def __init__(self, **kwargs):
            assert kwargs['endpoint'] == _VALUES.endpoint
            assert kwargs['secret_id'] == _VALUES.secret_id

        def login(self):
            calls.append('login')
            return 'fixture-token'

    monkeypatch.setattr(service, '_require_connection', lambda values: None)
    monkeypatch.setattr(service, 'OpenBaoClient', Client)
    monkeypatch.setattr(service, '_require_current_cluster', lambda client, **kw: calls.append('cluster'))
    monkeypatch.setattr(service, '_verify_inspection_authority', lambda client, token, **kw: calls.append('lookup'))
    assert service.verify_connection(_VALUES) is None
    assert calls == ['cluster', 'login', 'lookup', 'cluster']
    assert _VALUES.secret_id not in repr(_VALUES)


def test_openbao_runtime_cannot_build_generic_client(local_context):
    row = OpenBaoInstance()
    row.id = 7
    with pytest.raises(ValueError):
        runtime_adapter.execute('client.build', row)


def test_openbao_runtime_uses_provider_qualified_history_identity(local_context):
    identity = IntegrationInstance()
    identity.name = 'Fixture Bao'
    identity.provider_key = 'openbao'
    identity.adapter_key = 'openbao_http_v1'
    identity.integration_type = 'secrets_pki'
    identity.enabled = True
    identity.lifecycle_status = 'active'
    identity.health_status = 'connected'
    identity.readiness_status = 'degraded'
    row = OpenBaoInstance()
    row.id = 7
    row.ownership = 'external'
    row.integration_instance = identity
    state = runtime_adapter.get_state(row)
    assert state.provider_key == 'openbao'
    assert state.instance_id == 'openbao:7'
    assert state.readiness != 'ready'
