"""Metadata-only OpenBao collection through the canonical commit boundary."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from cryptography.fernet import Fernet
from flask import Flask
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki import commit_inventory

from app.integrations.secrets_management.secrets_pki.providers.kv2_metadata import (
    KV2CollectionEvidence,
    KV2SecretEvidence,
    KV2VersionEvidence,
    collect_kv2_metadata_with_token,
)
from app.integrations.secrets_management.secrets_pki.providers.kv2_http import SecretProviderError
from app.integrations.secrets_management.secrets_pki.providers.openbao import inventory
from app.integrations.secrets_management.secrets_pki.providers.openbao.inventory_scope import (
    LocalOpenBaoInventoryScope,
    resolve_local_inventory_scope,
)
from app.models.integration import IntegrationInstance
from app.models.openbao import OpenBaoInstance
from app.models.secrets_pki import (
    SecretIdentity,
    SecretInventoryCollectionState,
    SecretProviderRepresentation,
    SecretVersionObservation,
)


def test_openbao_metadata_traversal_does_not_access_data_or_login():
    transport = Mock()
    transport._request.side_effect = [
        (200, {'data': {'keys': ['ssh']}}),
        (200, {'data': {'current_version': 1, 'oldest_version': 1, 'max_versions': 10,
                         'cas_required': True, 'versions': {'1': {'created_time': '2026-11-27T00:00:00Z',
                         'deletion_time': '', 'destroyed': False}}}}),
    ]
    evidence = collect_kv2_metadata_with_token(transport, mount='fixture', token='fixture-token')
    assert len(evidence.records) == 1
    assert evidence.records[0].current_version == 1
    assert [call.args[0] for call in transport._request.call_args_list] == [
        '/v1/fixture/metadata', '/v1/fixture/metadata/ssh'
    ]
    transport.login.assert_not_called()


def test_mount_type_drift_denies_collection():
    transport = Mock()
    transport._request.return_value = (200, {'data': {'fixture/': {'type': 'kv', 'options': {'version': '1'}}}})
    scope = LocalOpenBaoInventoryScope(1, 'fixture', 'https://bao.example.invalid', 'fixture', 'external')
    with pytest.raises(SecretProviderError):
        inventory._require_mount(transport, scope, 'fixture-token')


@pytest.fixture
def store(monkeypatch):
    app = Flask(__name__)
    app.config.update(
        APP_ENV='development',
        SECRET_KEY='fixture-only',
        SQLALCHEMY_DATABASE_URI='sqlite://',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        INTEGRATION_CREDENTIAL_KEY=Fernet.generate_key().decode('ascii'),
    )
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('KAORI_LOCAL_OPENBAO_INVENTORY_MOUNT', 'fixture')
    db.init_app(app)
    with app.app_context():
        tables = [
            IntegrationInstance.__table__,
            OpenBaoInstance.__table__,
            SecretIdentity.__table__,
            SecretProviderRepresentation.__table__,
            SecretVersionObservation.__table__,
            SecretInventoryCollectionState.__table__,
        ]
        db.Model.metadata.create_all(bind=db.engine, tables=tables)
        identity = IntegrationInstance(
            integration_type='secrets_pki',
            provider_key='openbao',
            adapter_key='openbao_http_v1',
            name='fixture-openbao',
            enabled=True,
            lifecycle_status='active',
            readiness_status='degraded',
        )
        db.session.add(identity)
        db.session.flush()
        db.session.add(
            OpenBaoInstance(
                integration_instance_id=identity.id,
                ownership='external',
                endpoint='https://bao.example.invalid',
                cluster_id='4f6db34e-2042-4f0c-a385-a0d39582acb8',
                auth_mount='approle',
                role_id='fixture',
                secret_id='fixture-only',
            )
        )
        db.session.commit()
        monkeypatch.setenv('KAORI_LOCAL_OPENBAO_INVENTORY_PROVIDER_ID', str(identity.id))
        scope = resolve_local_inventory_scope(identity.id, 'fixture')
        audit = Mock()
        monkeypatch.setattr(commit_inventory, 'stage_operational_activity', audit)
        try:
            yield scope, audit
        finally:
            db.session.remove()
            db.Model.metadata.drop_all(bind=db.engine, tables=list(reversed(tables)))


def _snapshot(at, version=1):
    return KV2CollectionEvidence(
        mount='fixture',
        observed_at=at,
        records=(
            KV2SecretEvidence(
                mount='fixture',
                path='ssh',
                current_version=version,
                oldest_version=1,
                max_versions=10,
                cas_required=True,
                versions=(KV2VersionEvidence(version, at.isoformat(), None, False),),
            ),
        ),
    )


def test_canonical_openbao_commit_preserves_identity_and_nonready_posture(store):
    scope, audit = store
    at = datetime.now(UTC)
    assert commit_inventory.commit_local_openbao_inventory(scope, _snapshot(at)).observed_secret_count == 1
    row = SecretProviderRepresentation.query.one()
    secret_id = row.secret_identity_id
    assert row.provider_key == 'openbao'
    commit_inventory.commit_local_openbao_inventory(scope, _snapshot(at + timedelta(seconds=1), 2))
    assert SecretProviderRepresentation.query.one().secret_identity_id == secret_id
    assert SecretVersionObservation.query.count() == 2
    assert db.session.get(IntegrationInstance, scope.instance_id).readiness_status == 'degraded'
    assert audit.call_count == 2


def test_audit_failure_rolls_back_entire_collection(store):
    scope, audit = store
    audit.side_effect = SQLAlchemyError('fixture failure')
    with pytest.raises(SQLAlchemyError):
        commit_inventory.commit_local_openbao_inventory(scope, _snapshot(datetime.now(UTC)))
    assert SecretIdentity.query.count() == 0
    assert SecretProviderRepresentation.query.count() == 0
    assert SecretInventoryCollectionState.query.count() == 0


@pytest.mark.parametrize('changed', [{'mount': 'other'}, {'cluster_id': 'foreign'}, {'endpoint': 'https://foreign.invalid'}])
def test_changed_scope_cannot_commit(store, changed):
    scope, audit = store
    with pytest.raises(ValueError):
        commit_inventory.commit_local_openbao_inventory(replace(scope, **changed), _snapshot(datetime.now(UTC)))
    assert SecretProviderRepresentation.query.count() == 0
    audit.assert_not_called()


def test_vault_commit_entrypoint_cannot_commit_openbao(store):
    scope, audit = store
    with pytest.raises(ValueError):
        commit_inventory.commit_kv2_inventory(scope.instance_id, _snapshot(datetime.now(UTC)))
    assert SecretProviderRepresentation.query.count() == 0
    audit.assert_not_called()
