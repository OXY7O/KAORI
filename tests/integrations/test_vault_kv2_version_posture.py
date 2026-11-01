"""Committed KV v2 version posture does not infer rotation or expose paths."""

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from flask import Flask

from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.models.secrets_pki import (
    SecretIdentity,
    SecretInventoryCollectionState,
    SecretProviderRepresentation,
    SecretVersionObservation,
)
from app.models.vault import VaultInstance
from app.secrets_pki.kv2_version_posture import build_kv2_version_posture

AT = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


@pytest.fixture
def committed_store():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY='test-only',
        SQLALCHEMY_DATABASE_URI='sqlite://',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        INTEGRATION_CREDENTIAL_KEY=Fernet.generate_key().decode('ascii'),
    )
    db.init_app(app)
    with app.app_context():
        tables = [
            IntegrationInstance.__table__,
            VaultInstance.__table__,
            SecretIdentity.__table__,
            SecretProviderRepresentation.__table__,
            SecretVersionObservation.__table__,
            SecretInventoryCollectionState.__table__,
        ]
        db.Model.metadata.create_all(bind=db.engine, tables=tables)
        source = IntegrationInstance(
            integration_type='secrets_pki',
            provider_key='vault',
            adapter_key='vault_http_v1',
            name='hidden-vault',
            environment='testing',
            enabled=True,
            lifecycle_status='active',
            readiness_status='ready',
        )
        db.session.add(source)
        db.session.flush()
        vault = VaultInstance(
            integration_instance_id=source.id,
            endpoint='https://vault.invalid',
            auth_mount='approle',
            role_id='fixture',
            secret_id='fake-test-credential',
            timeout=5,
            verify_ssl=True,
            kv2_mounts=['secret'],
        )
        state = SecretInventoryCollectionState(
            integration_instance_id=source.id,
            provider_namespace='',
            mount='secret',
            status='ready',
            observed_count=0,
            last_observed_at=AT,
            last_committed_at=AT,
        )
        db.session.add_all([vault, state])
        db.session.commit()
        try:
            yield source.id, state
        finally:
            db.session.remove()
            db.Model.metadata.drop_all(bind=db.engine, tables=list(reversed(tables)))


def _read():
    return build_kv2_version_posture(now=AT + timedelta(minutes=5))


def _add_secret(source_id, state, *, deletion_time=None, destroyed=False):
    item = SecretProviderRepresentation(
        secret_identity=SecretIdentity(lifecycle_status='discovered'),
        integration_instance_id=source_id,
        provider_key='vault',
        provider_namespace='',
        mount='secret',
        path='private/secret-path-must-never-appear',
        path_sha256='a' * 64,
        representation_role='material_authority',
        observation_status='observed',
        current_version=1,
        oldest_version=1,
        max_versions=0,
        cas_required=True,
        last_observed_at=AT,
    )
    db.session.add(item)
    db.session.flush()
    db.session.add(
        SecretVersionObservation(
            representation_id=item.id,
            version=1,
            destroyed=destroyed,
            provider_deletion_time=deletion_time,
            last_observed_at=AT,
        )
    )
    state.observed_count += 1
    db.session.commit()
    return item


def test_true_empty_only_after_fresh_complete_committed_scan(committed_store):
    result = _read()
    assert result['status'] == 'observed_empty'
    assert result['observed_versions'] == 0
    assert result['available'] == 0


@pytest.mark.parametrize(
    ('deletion_time', 'destroyed', 'expected'),
    [
        (None, False, 'available'),
        ('2026-10-23T00:00:00Z', False, 'scheduled_deletion'),
        ('2026-10-21T00:00:00Z', False, 'soft_deleted'),
        (None, True, 'destroyed'),
        ('not-a-date', False, 'unknown'),
    ],
)
def test_version_posture_uses_committed_metadata_only(committed_store, deletion_time, destroyed, expected):
    source_id, state = committed_store
    _add_secret(source_id, state, deletion_time=deletion_time, destroyed=destroyed)
    result = _read()
    assert result['status'] == 'ready'
    assert result['observed_versions'] == 1
    assert result[expected] == 1
    assert 'private/' not in repr(result)
    assert 'secret-path' not in repr(result)
    assert 'fake-test-credential' not in repr(result)
    assert 'secret_identity_id' not in result


def test_stale_and_failed_collection_never_claim_zero(committed_store):
    _, state = committed_store
    state.status = 'stale'
    db.session.commit()
    result = _read()
    assert result['status'] == 'incomplete_evidence'
    assert result['observed_versions'] is None
    state.status = 'ready'
    state.last_committed_at = AT - timedelta(days=2)
    db.session.commit()
    assert _read()['observed_versions'] is None


def test_mount_scope_revocation_and_disabled_provider_exclude_evidence(committed_store):
    source_id, state = committed_store
    _add_secret(source_id, state)
    vault = VaultInstance.query.filter_by(integration_instance_id=source_id).one()
    vault.kv2_mounts = []
    db.session.commit()
    assert _read()['status'] == 'not_configured'
    vault.kv2_mounts = ['secret']
    db.session.get(IntegrationInstance, source_id).enabled = False
    db.session.commit()
    assert _read()['observed_versions'] is None


def test_missing_or_conflicting_generation_returns_unknown_not_zero(committed_store):
    source_id, state = committed_store
    record = _add_secret(source_id, state)
    state.observed_count = 2
    db.session.commit()
    assert _read()['status'] == 'incomplete_evidence'
    state.observed_count = 1
    record.last_observed_at = AT - timedelta(days=1)
    db.session.commit()
    assert _read()['status'] == 'incomplete_evidence'


def test_historical_version_not_current_is_not_copied_into_posture(committed_store):
    source_id, state = committed_store
    record = _add_secret(source_id, state)
    version = SecretVersionObservation.query.filter_by(representation_id=record.id).one()
    version.last_observed_at = AT - timedelta(days=1)
    db.session.commit()
    result = _read()
    assert result['status'] == 'incomplete_evidence'
    assert result['available'] is None


def test_historical_not_observed_secret_does_not_count_as_current(committed_store):
    source_id, state = committed_store
    record = _add_secret(source_id, state)
    record.observation_status = 'not_observed'
    state.observed_count = 0
    db.session.commit()
    result = _read()
    assert result['status'] == 'observed_empty'
    assert result['observed_versions'] == 0


def test_missing_source_scan_is_not_a_valid_zero(committed_store):
    _, state = committed_store
    state.last_observed_at = None
    db.session.commit()
    assert _read()['status'] == 'incomplete_evidence'
    assert _read()['available'] is None


@pytest.mark.parametrize('field', ['last_committed_at', 'last_observed_at'])
def test_future_source_timestamp_blocks_empty_snapshot(committed_store, field):
    _, state = committed_store
    setattr(state, field, AT + timedelta(hours=1))
    db.session.commit()
    result = _read()
    assert result['status'] == 'incomplete_evidence'
    assert result['observed_versions'] is None
    assert result['available'] is None


def test_future_commit_cannot_qualify_observed_versions(committed_store):
    source_id, state = committed_store
    _add_secret(source_id, state)
    state.last_committed_at = AT + timedelta(hours=1)
    db.session.commit()
    result = _read()
    assert result['status'] == 'incomplete_evidence'
    assert result['observed_versions'] is None
    assert result['destroyed'] is None
