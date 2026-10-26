from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from flask import Flask

from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki.commit_inventory import (
    commit_kv2_inventory,
    mark_kv2_inventory_failed,
)
from app.integrations.secrets_management.secrets_pki.inventory_presentation import vault_inventory_readiness
from app.integrations.secrets_management.secrets_pki.providers.vault.kv2_inventory import (
    KV2CollectionEvidence,
    KV2SecretEvidence,
    KV2VersionEvidence,
)
from app.models.integration import IntegrationInstance
from app.models.secrets_pki import (
    SecretIdentity,
    SecretInventoryCollectionState,
    SecretProviderRepresentation,
    SecretVersionObservation,
)
from app.models.vault import VaultInstance


@pytest.fixture
def store():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY='only-for-test',
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
        identity = IntegrationInstance(
            integration_type='secrets_pki',
            provider_key='vault',
            adapter_key='vault_http_v1',
            name='test-vault',
            environment='testing',
            enabled=True,
            readiness_status='ready',
        )
        db.session.add(identity)
        db.session.flush()
        connection = VaultInstance(
            integration_instance_id=identity.id,
            endpoint='https://vault.example.test',
            auth_mount='approle',
            role_id='reader',
            secret_id='test-only',
            timeout=5,
            verify_ssl=True,
            kv2_mounts=['secret'],
        )
        db.session.add(connection)
        db.session.commit()
        try:
            yield identity.id
        finally:
            db.session.remove()
            db.Model.metadata.drop_all(bind=db.engine, tables=list(reversed(tables)))


def _snapshot(at: datetime, names=('team/db',), *, version=1, complete=True):
    return KV2CollectionEvidence(
        mount='secret',
        observed_at=at,
        complete=complete,
        records=tuple(
            KV2SecretEvidence(
                mount='secret',
                path=name,
                current_version=version,
                oldest_version=1,
                max_versions=0,
                cas_required=True,
                versions=(
                    KV2VersionEvidence(
                        version=version,
                        created_time='2026-10-22T00:00:00Z',
                        deletion_time=None,
                        destroyed=False,
                    ),
                ),
            )
            for name in names
        ),
    )


def test_initial_commit_and_refresh_preserve_canonical_secret_identity_and_history(store):
    first_time = datetime(2026, 10, 22, tzinfo=UTC)
    first = commit_kv2_inventory(store, _snapshot(first_time))
    assert first.observed_secret_count == 1
    row = SecretProviderRepresentation.query.one()
    canonical_id = row.secret_identity_id
    assert row.path == 'team/db'
    assert row.observation_status == 'observed'
    assert SecretVersionObservation.query.count() == 1

    second = commit_kv2_inventory(store, _snapshot(first_time + timedelta(minutes=5), version=2))
    assert second.observed_secret_count == 1
    assert SecretProviderRepresentation.query.count() == 1
    assert SecretProviderRepresentation.query.one().secret_identity_id == canonical_id
    assert SecretVersionObservation.query.count() == 2
    assert {item.version for item in SecretVersionObservation.query.all()} == {1, 2}
    assert SecretIdentity.query.count() == 1


def test_unexpected_empty_collection_cannot_delete_committed_evidence(store):
    now = datetime(2026, 10, 22, tzinfo=UTC)
    commit_kv2_inventory(store, _snapshot(now))
    with pytest.raises(ValueError, match='empty'):
        commit_kv2_inventory(store, _snapshot(now + timedelta(minutes=1), names=()))
    assert SecretProviderRepresentation.query.count() == 1
    state = SecretInventoryCollectionState.query.one()
    assert state.status == 'ready'
    assert state.observed_count == 1


def test_partial_or_older_collection_is_never_promoted(store):
    now = datetime(2026, 10, 22, tzinfo=UTC)
    commit_kv2_inventory(store, _snapshot(now))
    with pytest.raises(ValueError, match='Incomplete'):
        commit_kv2_inventory(store, _snapshot(now + timedelta(minutes=1), complete=False))
    with pytest.raises(ValueError, match='older'):
        commit_kv2_inventory(store, _snapshot(now - timedelta(minutes=1)))
    assert SecretProviderRepresentation.query.count() == 1
    assert SecretInventoryCollectionState.query.one().observed_count == 1


def test_missing_from_later_complete_snapshot_is_not_provider_deletion(store):
    now = datetime(2026, 10, 22, tzinfo=UTC)
    commit_kv2_inventory(store, _snapshot(now, names=('team/db', 'team/cache')))
    result = commit_kv2_inventory(store, _snapshot(now + timedelta(minutes=1), names=('team/db',)))
    assert result.not_observed_count == 1
    status_by_path = {r.path: r.observation_status for r in SecretProviderRepresentation.query.all()}
    assert status_by_path == {'team/db': 'observed', 'team/cache': 'not_observed'}
    assert SecretIdentity.query.count() == 2


def test_disabled_vault_connection_cannot_commit_even_with_evidence(store):
    row = VaultInstance.query.filter_by(integration_instance_id=store).one()
    row.enabled = False
    db.session.commit()
    with pytest.raises(ValueError, match='not eligible'):
        commit_kv2_inventory(store, _snapshot(datetime(2026, 10, 22, tzinfo=UTC)))
    assert SecretProviderRepresentation.query.count() == 0


def test_revoked_mount_config_cannot_commit_new_evidence(store):
    now = datetime(2026, 10, 22, tzinfo=UTC)
    commit_kv2_inventory(store, _snapshot(now))
    instance = VaultInstance.query.filter_by(integration_instance_id=store).one()
    instance.kv2_mounts = []
    db.session.commit()
    with pytest.raises(ValueError, match='not eligible'):
        commit_kv2_inventory(store, _snapshot(now + timedelta(minutes=1)))
    assert SecretInventoryCollectionState.query.one().observed_count == 1
    assert SecretProviderRepresentation.query.one().observation_status == 'observed'


def test_failed_provider_scan_keeps_history_but_marks_stale(store):
    now = datetime(2026, 10, 22, tzinfo=UTC)
    commit_kv2_inventory(store, _snapshot(now))
    previous_commit = SecretInventoryCollectionState.query.one().last_committed_at
    mark_kv2_inventory_failed(store, 'secret')
    state = SecretInventoryCollectionState.query.one()
    assert state.status == 'stale'
    assert state.last_committed_at == previous_commit
    assert state.observed_count == 1
    assert state.last_error and 'SecretID' not in state.last_error
    assert SecretProviderRepresentation.query.count() == 1
    commit_kv2_inventory(store, _snapshot(now + timedelta(minutes=2)))
    state = SecretInventoryCollectionState.query.one()
    assert state.status == 'ready'
    assert state.last_error is None


def test_unapproved_mount_failure_does_not_create_collection_state(store):
    mark_kv2_inventory_failed(store, 'unapproved')
    assert SecretInventoryCollectionState.query.count() == 0


def test_admin_readiness_projection_reads_committed_state_without_provider_calls(store):
    instance = VaultInstance.query.filter_by(integration_instance_id=store).one()
    before = vault_inventory_readiness(instance)
    assert before['state'] == 'not_collected'
    assert before['observed_secret_count'] is None
    assert before['committed_mount_count'] == 0

    observed = datetime(2026, 10, 22, tzinfo=UTC)
    commit_kv2_inventory(store, _snapshot(observed))
    ready = vault_inventory_readiness(instance)
    assert ready['state'] == 'ready'
    assert ready['approved_mount_count'] == 1
    assert ready['committed_mount_count'] == 1
    assert ready['observed_secret_count'] == 1
    assert ready['last_committed_at'] is not None

    mark_kv2_inventory_failed(store, 'secret')
    stale = vault_inventory_readiness(instance)
    assert stale['state'] == 'stale'
    assert stale['observed_secret_count'] == 1

    instance.kv2_mounts = []
    db.session.commit()
    disabled = vault_inventory_readiness(instance)
    assert disabled['state'] == 'not_configured'
    assert disabled['observed_secret_count'] is None


def test_version_counter_regression_does_not_reassign_existing_secret_identity(store):
    at = datetime(2026, 10, 22, tzinfo=UTC)
    commit_kv2_inventory(store, _snapshot(at, version=2))
    identity_id = SecretProviderRepresentation.query.one().secret_identity_id
    with pytest.raises(ValueError, match='regressed'):
        commit_kv2_inventory(store, _snapshot(at + timedelta(minutes=1), version=1))
    representation = SecretProviderRepresentation.query.one()
    assert representation.secret_identity_id == identity_id
    assert representation.current_version == 2


def test_destroyed_version_evidence_cannot_revert_to_not_destroyed(store):
    at = datetime(2026, 10, 22, tzinfo=UTC)
    initial = _snapshot(at)
    secret = initial.records[0]
    destroyed = replace(
        initial,
        records=(
            replace(
                secret,
                versions=(replace(secret.versions[0], destroyed=True),),
            ),
        ),
    )
    commit_kv2_inventory(store, destroyed)
    with pytest.raises(ValueError, match='cannot reverse'):
        commit_kv2_inventory(store, _snapshot(at + timedelta(minutes=1)))
    assert SecretVersionObservation.query.one().destroyed is True


def test_inactive_provider_identity_is_not_admitted_even_with_stale_ready_metadata(store):
    identity = db.session.get(IntegrationInstance, store)
    identity.lifecycle_status = 'retired'
    db.session.commit()
    with pytest.raises(ValueError, match='not eligible'):
        commit_kv2_inventory(store, _snapshot(datetime(2026, 10, 22, tzinfo=UTC)))
    assert SecretProviderRepresentation.query.count() == 0


def test_foreign_provider_cannot_use_vault_inventory_commit_path(store):
    identity = db.session.get(IntegrationInstance, store)
    identity.provider_key = 'other'
    db.session.commit()
    with pytest.raises(ValueError, match='not eligible'):
        commit_kv2_inventory(store, _snapshot(datetime(2026, 10, 22, tzinfo=UTC)))
    assert SecretProviderRepresentation.query.count() == 0
