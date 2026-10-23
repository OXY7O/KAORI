"""GitHub App shared credential, grant isolation and encrypted-at-rest checks (#2741)."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, insert, select, text

from app.integrations.source_control.source_control.providers.github.credential_service import (
    build_client_for_installation,
)
from app.integrations.source_control.source_control.providers.github.transport import GitHubProviderError
from app.models.source_control import GitHubAppCredential


def _installation(*, enabled: bool = True, credential_app: str = '4',
                  installation_app: str = '4', host: str = 'github.com'):
    return SimpleNamespace(
        integration_instance_id=12,
        integration_instance=SimpleNamespace(
            id=12, integration_type='source_control', provider_key='github',
            adapter_key='github_rest_v3', lifecycle_status='active', enabled=True,
        ),
        github_app_credential=SimpleNamespace(
            native_app_id=credential_app, private_key_pem='pem-value',
            host_key='github.com', enabled=enabled,
        ),
        provider_key='github', host_key=host, native_app_id=installation_app,
        account=SimpleNamespace(native_account_id='8'),
    )


def test_client_builder_reuses_approved_app_config_without_network() -> None:
    installation = _installation()
    client = build_client_for_installation(installation)
    assert client.app_id == 4


@pytest.mark.parametrize('change', [
    {'enabled': False},
    {'credential_app': '3'},
    {'installation_app': '5'},
    {'host': 'ghes.internal'},
])
def test_cross_app_or_disabled_grant_is_denied(change) -> None:
    with pytest.raises(GitHubProviderError, match='not eligible'):
        build_client_for_installation(_installation(**change))


def test_sso_connection_cannot_be_used_as_source_control_provider() -> None:
    installation = _installation()
    installation.integration_instance.integration_type = 'identity_provider'
    with pytest.raises(GitHubProviderError):
        build_client_for_installation(installation)


def test_one_encrypted_app_config_can_be_shared_by_multiple_installations(monkeypatch) -> None:
    monkeypatch.setattr(
        'app.security.credentials._configured_secrets',
        lambda: ('unit-test-github-app-credential-key',),
    )
    engine = create_engine('sqlite+pysqlite:///:memory:')
    try:
        GitHubAppCredential.__table__.create(bind=engine)
        private_key = '-----BEGIN PRIVATE KEY----- test-fixture'
        webhook = 'test-webhook-secret'
        now = datetime.now(UTC)
        with engine.begin() as connection:
            connection.execute(insert(GitHubAppCredential).values(
                host_key='github.com', native_app_id='123',
                private_key_pem=private_key, webhook_secret=webhook,
                enabled=True, created_at=now, updated_at=now,
            ))
            raw = connection.execute(
                text('SELECT private_key_pem, webhook_secret FROM source_control_github_app_credentials')
            ).one()
            assert raw[0].startswith('enc:v1:')
            assert raw[1].startswith('enc:v1:')
            assert private_key not in raw[0]
            assert webhook not in raw[1]
            record = connection.execute(select(
                GitHubAppCredential.private_key_pem, GitHubAppCredential.webhook_secret
            )).one()
            assert record == (private_key, webhook)
    finally:
        engine.dispose()


def test_app_credential_representation_never_exposes_secret() -> None:
    record = GitHubAppCredential(
        id=7, host_key='github.com', native_app_id='123',
        private_key_pem='secret-pem', webhook_secret='secret-hook', enabled=False,
    )
    assert 'secret-pem' not in repr(record)
    assert 'secret-hook' not in repr(record)


def test_migration_follows_sc01_identity_head_and_does_not_seed_secrets() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    migration = (
        root / 'migrations/versions/20261023_source_control_app_credentials.py'
    ).read_text()
    assert "down_revision = '20261023_sc_identity'" in migration
    assert 'source_control_github_app_credentials' in migration
    assert 'private_key_pem' in migration and 'webhook_secret' in migration
    assert 'INSERT INTO' not in migration.upper()
