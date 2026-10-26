"""Source-scoped Vault Secret registry preparation stays unavailable without #724."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

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
from app.secrets_pki.scoped_registry import (
    ScopedRegistryDecision,
    read_scoped_secret_registry,
)

AT = datetime(2026, 10, 22, 12, tzinfo=UTC)
ACTOR_ID = 37


@pytest.fixture
def registry_source():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY='fixture-only',
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
        provider = IntegrationInstance(
            integration_type='secrets_pki',
            provider_key='vault',
            adapter_key='vault_http_v1',
            name='super-secret-provider-name',
            environment='testing',
            enabled=True,
            lifecycle_status='active',
            readiness_status='ready',
        )
        db.session.add(provider)
        db.session.flush()
        db.session.add(
            VaultInstance(
                integration_instance_id=provider.id,
                endpoint='https://vault.invalid',
                auth_mount='approle',
                role_id='fixture',
                secret_id='fixture-value-only',
                timeout=5,
                verify_ssl=True,
                kv2_mounts=['secret'],
                namespace='',
            )
        )
        db.session.add(
            SecretInventoryCollectionState(
                integration_instance_id=provider.id,
                provider_namespace='',
                mount='secret',
                status='ready',
                observed_count=0,
                last_observed_at=AT,
                last_committed_at=AT,
            )
        )
        db.session.commit()
        try:
            yield provider.id
        finally:
            db.session.remove()
            db.Model.metadata.drop_all(bind=db.engine, tables=list(reversed(tables)))


def _decision(provider_id):
    return ScopedRegistryDecision(
        actor_id=ACTOR_ID,
        instance_id=provider_id,
        provider_namespace='',
        mount='secret',
        permission_allowed=True,
        resource_allowed=True,
        decision_authority='resource_scope_policy',
        policy_reference=str(uuid4()),
        evaluated_at=AT,
        expires_at=AT + timedelta(minutes=10),
    )


def _read(decision, *, actor_id=ACTOR_ID, page=1, per_page=5, now=None):
    return read_scoped_secret_registry(
        decision=decision,
        actor_id=actor_id,
        page=page,
        per_page=per_page,
        now=now or AT + timedelta(minutes=2),
    )


def _add_records(provider_id, n):
    state = SecretInventoryCollectionState.query.filter_by(integration_instance_id=provider_id).one()
    for i in range(n):
        private_path = f'very/sensitive/path{str(i)}'
        representation = SecretProviderRepresentation(
            secret_identity=SecretIdentity(lifecycle_status='discovered'),
            integration_instance_id=provider_id,
            provider_key='vault',
            provider_namespace='',
            mount='secret',
            path=private_path,
            path_sha256=sha256(private_path.encode()).hexdigest(),
            representation_role='material_authority',
            observation_status='observed',
            current_version=3,
            oldest_version=1,
            max_versions=0,
            cas_required=True,
            last_observed_at=AT,
        )
        db.session.add(representation)
        db.session.flush()
        db.session.add(
            SecretVersionObservation(
                representation_id=representation.id,
                version=3,
                destroyed=False,
                last_observed_at=AT,
            )
        )
    state.observed_count = n
    db.session.commit()


def test_no_scope_decision_is_non_enumerating_even_if_aggregate_inventory_exists(registry_source):
    _add_records(registry_source, 2)
    page = _read(None)
    assert page.status == 'scope_required'
    assert page.total_items is None and page.rows == ()
    assert page.total_pages is None


@pytest.mark.parametrize(
    'change',
    [
        {'permission_allowed': False},
        {'resource_allowed': False},
        {'decision_authority': 'unavailable'},
        {'policy_reference': None},
        {'actor_id': 88},
        {'expires_at': AT - timedelta(minutes=1)},
        {'evaluated_at': AT - timedelta(minutes=20)},
        {'provider_namespace': 'other'},
        {'mount': 'other-mount'},
    ],
)
def test_missing_expired_or_wrong_scoped_authority_never_exposes_rows(registry_source, change):
    _add_records(registry_source, 1)
    result = _read(replace(_decision(registry_source), **change))
    assert result.rows == ()
    assert result.total_items is None
    assert result.status in ('scope_required', 'source_unavailable')


def test_actor_id_mismatch_and_guessed_instance_cannot_read(registry_source):
    _add_records(registry_source, 1)
    assert _read(_decision(registry_source), actor_id=ACTOR_ID + 1).status == 'scope_required'
    assert _read(replace(_decision(registry_source), instance_id=registry_source + 990)).status == 'source_unavailable'


def test_authorized_scope_has_bounded_stable_server_pagination_and_no_vault_path(registry_source):
    _add_records(registry_source, 7)
    decision = _decision(registry_source)
    first, second = _read(decision), _read(decision, page=2)
    assert first.status == second.status == 'ready'
    assert first.total_items == second.total_items == 7
    assert first.total_pages == 2
    assert len(first.rows) == 5 and len(second.rows) == 2
    assert len({row.secret_identity_id for row in (*first.rows, *second.rows)}) == 7
    assert all(row.observed_version_count == 1 and row.cas_required for row in first.rows)
    assert 'very/sensitive/' not in repr((first, second))
    assert 'super-secret-provider-name' not in repr((first, second))
    assert 'fixture-value-only' not in repr((first, second))
    assert 'path' not in repr(first).lower()


def test_authorized_empty_requires_committed_ready_scan(registry_source):
    decision = _decision(registry_source)
    assert _read(decision).total_items == 0
    state = SecretInventoryCollectionState.query.one()
    state.status = 'failed'
    db.session.commit()
    assert _read(decision).total_items is None


def test_disabled_or_revoked_provider_scope_fail_closed(registry_source):
    _add_records(registry_source, 1)
    decision = _decision(registry_source)
    vault = VaultInstance.query.filter_by(integration_instance_id=registry_source).one()
    vault.kv2_mounts = []
    db.session.commit()
    assert _read(decision).total_items is None
    vault.kv2_mounts = ['secret']
    provider = db.session.get(IntegrationInstance, registry_source)
    provider.enabled = False
    db.session.commit()
    assert _read(decision).total_items is None


def test_stale_or_incomplete_generation_and_history_are_not_current_registry(registry_source):
    _add_records(registry_source, 1)
    decision = _decision(registry_source)
    state = SecretInventoryCollectionState.query.one()
    state.last_observed_at = AT - timedelta(days=2)
    db.session.commit()
    assert _read(decision).status == 'source_unavailable'
    state.last_observed_at = AT
    representation = SecretProviderRepresentation.query.one()
    representation.observation_status = 'not_observed'
    db.session.commit()
    assert _read(decision).total_items is None


def test_missing_current_version_readback_blocks_positive_page(registry_source):
    _add_records(registry_source, 1)
    decision = _decision(registry_source)
    SecretVersionObservation.query.delete()
    db.session.commit()
    assert _read(decision).status == 'source_unavailable'


@pytest.mark.parametrize(('page', 'per_page'), [(0, 5), (1, 8), (1, 100), (-1, 5)])
def test_unapproved_pagination_limits_are_denied(registry_source, page, per_page):
    result = _read(_decision(registry_source), page=page, per_page=per_page)
    assert result.status == 'scope_required'
    assert result.total_items is None
