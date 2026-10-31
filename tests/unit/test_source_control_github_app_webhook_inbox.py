"""SC-02 durable webhook ledger: signature, replay, scope and transaction boundaries."""

from __future__ import annotations

import hashlib
import hmac
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.integrations.source_control.source_control.providers.github import webhook_inbox
from app.integrations.source_control.source_control.providers.github.webhook import GitHubWebhookError
from app.models.integration import IntegrationInstance
from app.models.source_control import (
    GitHubAppCredential,
    SourceAccount,
    SourceInstallation,
    SourceWebhookDelivery,
)

_SECRET = 'local-signed-event-secret'
_UUID = '6d670ec2-5de8-11e8-bc12-18b6d4a166f7'


@pytest.fixture
def staged(monkeypatch):
    monkeypatch.setattr(
        'app.security.credentials._configured_secrets',
        lambda: ('unit-test-github-webhook-ledger-key',),
    )
    monkeypatch.setattr(webhook_inbox, 'provider_kind', lambda *_: SimpleNamespace(available=True))
    engine = create_engine('sqlite+pysqlite:///:memory:')
    IntegrationInstance.metadata.create_all(
        bind=engine,
        tables=[
            IntegrationInstance.__table__,
            SourceAccount.__table__,
            GitHubAppCredential.__table__,
            SourceInstallation.__table__,
            SourceWebhookDelivery.__table__,
        ],
    )
    with Session(engine) as session:
        app = GitHubAppCredential(
            host_key='github.com',
            native_app_id='42',
            private_key_pem='test-not-real-pem',
            webhook_secret=_SECRET,
            enabled=True,
        )
        account = SourceAccount(
            host_key='github.com',
            provider_key='github',
            native_account_id='78',
            account_type='Organization',
        )
        session.add_all((app, account))
        session.flush()

        identities = []
        for i in (1, 2):
            canonical = IntegrationInstance(
                integration_type='source_control',
                name=f'GitHub {i}',
                provider_key='github',
                adapter_key='github_rest_v3',
                lifecycle_status='active',
                readiness_status='validation_required',
                enabled=True,
            )
            session.add(canonical)
            session.flush()
            instance = SourceInstallation(
                integration_instance_id=canonical.id,
                provider_key='github',
                host_key='github.com',
                native_app_id='42',
                native_installation_id=str(i),
                github_app_credential_id=app.id,
                account_id=account.id,
                repository_scope='selected',
                grant_status='unknown',
            )
            session.add(instance)
            session.flush()
            identities.append(instance.id)
        session.commit()

        installations = [session.get(SourceInstallation, key) for key in identities]
        assert all(installations)
        yield session, installations
    engine.dispose()


def _payload(installation: int = 1, *, repo: int = 100) -> bytes:
    return json.dumps(
        {
            'installation': {'id': installation},
            'repository': {'id': repo},
            'action': 'completed',
        },
        separators=(',', ':'),
    ).encode()


def _headers(payload: bytes) -> dict[str, str]:
    digest = hmac.new(_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return {
        'X-Hub-Signature-256': 'sha256=' + digest,
        'Content-Type': 'application/json',
        'X-GitHub-Delivery': _UUID,
        'X-GitHub-Event': 'workflow_run',
    }


def test_authenticated_delivery_claim_persists_only_safe_metadata(staged):
    session, (installation, _) = staged
    payload = _payload()
    claim = webhook_inbox.claim_verified_delivery(
        installation=installation, payload=payload, headers=_headers(payload), session=session
    )
    assert claim.newly_staged
    assert claim.delivery_id == _UUID
    session.commit()
    row = session.execute(select(SourceWebhookDelivery)).scalar_one()
    assert row.installation_id == installation.id
    assert row.event_type == 'workflow_run'
    assert row.processing_state == 'received'
    assert row.payload_sha256 == hashlib.sha256(payload).hexdigest()
    assert row.repository_native_id_hint == '100'
    assert row.attempt_count == 0
    assert not hasattr(row, 'raw_payload')
    assert not hasattr(row, 'token')


def test_duplicate_delivery_is_idempotent_after_commit(staged):
    session, (installation, _) = staged
    payload = _payload()
    first = webhook_inbox.claim_verified_delivery(
        installation=installation, payload=payload, headers=_headers(payload), session=session
    )
    session.commit()
    second = webhook_inbox.claim_verified_delivery(
        installation=installation, payload=payload, headers=_headers(payload), session=session
    )
    assert first.newly_staged
    assert not second.newly_staged
    assert len(session.execute(select(SourceWebhookDelivery)).scalars().all()) == 1


def test_same_uuid_with_different_signed_payload_is_rejected(staged):
    session, (installation, _) = staged
    payload = _payload(repo=3)
    webhook_inbox.claim_verified_delivery(
        installation=installation, payload=payload, headers=_headers(payload), session=session
    )
    session.commit()
    changed = _payload(repo=4)
    with pytest.raises(GitHubWebhookError, match='different content'):
        webhook_inbox.claim_verified_delivery(
            installation=installation,
            payload=changed,
            headers=_headers(changed),
            session=session,
        )


def test_identical_github_delivery_id_is_qualified_by_installation(staged):
    session, (first, second) = staged
    for installation in (first, second):
        payload = _payload(installation=int(installation.native_installation_id))
        claim = webhook_inbox.claim_verified_delivery(
            installation=installation,
            payload=payload,
            headers=_headers(payload),
            session=session,
        )
        assert claim.newly_staged
        session.commit()
    assert len(session.execute(select(SourceWebhookDelivery)).scalars().all()) == 2


def test_invalid_signature_never_creates_ledger_record(staged):
    session, (installation, _) = staged
    payload = _payload()
    headers = _headers(payload)
    headers['X-Hub-Signature-256'] = 'sha256=' + 'a' * 64
    with pytest.raises(GitHubWebhookError):
        webhook_inbox.claim_verified_delivery(
            installation=installation, payload=payload, headers=headers, session=session
        )
    assert session.execute(select(SourceWebhookDelivery)).scalars().all() == []


def test_other_installation_is_denied_even_when_hmac_valid(staged):
    session, (installation, _) = staged
    payload = _payload(installation=2)
    with pytest.raises(GitHubWebhookError, match='does not match'):
        webhook_inbox.claim_verified_delivery(
            installation=installation, payload=payload, headers=_headers(payload), session=session
        )
    assert session.execute(select(SourceWebhookDelivery)).scalars().all() == []


def test_planned_provider_rejects_before_authenticated_ingress(staged, monkeypatch):
    session, (installation, _) = staged
    monkeypatch.setattr(webhook_inbox, 'provider_kind', lambda *_: SimpleNamespace(available=False))
    payload = _payload()
    with pytest.raises(GitHubWebhookError, match='not been admitted'):
        webhook_inbox.claim_verified_delivery(
            installation=installation, payload=payload, headers=_headers(payload), session=session
        )


def test_revoked_connection_denies_inbox(staged):
    session, (installation, _) = staged
    installation.integration_instance.enabled = False
    session.flush()
    payload = _payload()
    with pytest.raises(GitHubWebhookError, match='not eligible'):
        webhook_inbox.claim_verified_delivery(
            installation=installation, payload=payload, headers=_headers(payload), session=session
        )


def test_ledger_schema_includes_unique_scope_and_no_raw_body():
    table = SourceWebhookDelivery.__table__
    keys = {c.name for c in table.columns}
    assert {'installation_id', 'delivery_id', 'payload_sha256', 'processing_state'} <= keys
    assert not {'raw_payload', 'private_key_pem', 'authorization', 'token'} & keys
    assert any(
        set(constraint.columns.keys()) == {'installation_id', 'delivery_id'}
        for constraint in table.constraints
        if hasattr(constraint, 'columns')
    )


def test_inbox_does_not_dispatch_before_commit():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2]
        / 'app/integrations/source_control/source_control/providers/github/webhook_inbox.py'
    ).read_text()
    assert 'apply_async' not in source
    claim = source.split('def claim_verified_delivery(', 1)[1].split(
        'def stage_signed_github_webhook_delivery(', 1
    )[0]
    staging = source.split('def stage_signed_github_webhook_delivery(', 1)[1]
    assert 'db.session.commit()' not in claim
    assert staging.index('claim_verified_delivery(') < staging.index('db.session.commit()')
    assert 'db.session.rollback()' in staging
    assert 'Blueprint(' not in source
