"""Stored PKI certificate evidence is atomic, retained and scope-qualified."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from flask import Flask

from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki.commit_stored_certificates import (
    commit_stored_pki_certificates,
    mark_stored_pki_certificates_failed,
)
from app.integrations.secrets_management.secrets_pki.providers.vault.pki_public_evidence import (
    PublicCertificateEvidence,
)
from app.integrations.secrets_management.secrets_pki.providers.vault.pki_stored_certificates import (
    StoredCertificateCollection,
    StoredCertificateEvidence,
)
from app.models.integration import IntegrationInstance
from app.models.secrets_pki_stored_certificates import (
    PKIStoredCertificateCollectionState,
    PKIStoredCertificateObservation,
)
from app.models.vault import VaultInstance
from app.secrets_pki.pki_stored_presentation import stored_pki_certificate_readiness

DAY = datetime(2026, 10, 22, tzinfo=UTC)


@pytest.fixture
def store():
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
            PKIStoredCertificateObservation.__table__,
            PKIStoredCertificateCollectionState.__table__,
        ]
        db.Model.metadata.create_all(bind=db.engine, tables=tables)
        identity = IntegrationInstance(
            integration_type='secrets_pki',
            provider_key='vault',
            adapter_key='vault_http_v1',
            name='test-stored-certs',
            enabled=True,
            readiness_status='ready',
            environment='testing',
        )
        db.session.add(identity)
        db.session.flush()
        db.session.add(
            VaultInstance(
                integration_instance_id=identity.id,
                endpoint='https://vault.internal.invalid',
                auth_mount='approle',
                role_id='metadata-only',
                secret_id='test-only',
                timeout=5,
                verify_ssl=True,
                pki_mounts=['pki'],
                pki_stored_certs_enabled=True,
            )
        )
        db.session.commit()
        try:
            yield identity.id
        finally:
            db.session.remove()
            db.Model.metadata.drop_all(bind=db.engine, tables=list(reversed(tables)))


def _snapshot(when=DAY, *, serial='65', fingerprint='a' * 64, empty=False, complete=True):
    certificate = PublicCertificateEvidence(
        fingerprint_sha256=fingerprint,
        serial_hex=serial,
        subject='CN=internal-private-tenant',
        issuer='CN=not-for-ui',
        valid_from=DAY - timedelta(days=2),
        valid_until=DAY + timedelta(days=100),
        is_ca=False,
        self_issued=False,
        dns_names=('private.example',),
    )
    return StoredCertificateCollection(
        mount='pki',
        observed_at=when,
        certificates=()
        if empty
        else (
            StoredCertificateEvidence(
                serial_hex=serial,
                certificate=certificate,
            ),
        ),
        complete=complete,
    )


def test_successful_commit_and_repeat_do_not_duplicate(store):
    initial = commit_stored_pki_certificates(store, _snapshot())
    assert initial.observed_count == 1
    assert PKIStoredCertificateObservation.query.count() == 1
    repeated = commit_stored_pki_certificates(store, _snapshot(DAY + timedelta(minutes=1)))
    assert repeated.observed_count == 1
    assert PKIStoredCertificateObservation.query.count() == 1
    assert PKIStoredCertificateObservation.query.one().observation_status == 'observed'


def test_missing_uncommitted_is_unknown_but_real_committed_zero_is_zero(store):
    instance = VaultInstance.query.filter_by(integration_instance_id=store).one()
    missing = stored_pki_certificate_readiness(instance=instance)
    assert missing['state'] == 'not_collected'
    assert missing['observed_certificates'] is None
    commit_stored_pki_certificates(store, _snapshot(empty=True))
    observed = stored_pki_certificate_readiness(instance=instance)
    assert observed['state'] == 'committed'
    assert observed['observed_certificates'] == 0
    assert observed['coverage'] == 'vault_stored_only'


def test_unexpected_empty_after_nonempty_and_incomplete_snapshot_fail_closed(store):
    commit_stored_pki_certificates(store, _snapshot())
    with pytest.raises(ValueError, match='empty'):
        commit_stored_pki_certificates(store, _snapshot(DAY + timedelta(minutes=1), empty=True))
    with pytest.raises(ValueError, match='incomplete'):
        commit_stored_pki_certificates(store, _snapshot(DAY + timedelta(minutes=1), complete=False))
    assert PKIStoredCertificateObservation.query.one().observation_status == 'observed'


def test_immutability_and_out_of_order_readback_rejected(store):
    commit_stored_pki_certificates(store, _snapshot())
    with pytest.raises(ValueError, match='Out-of-order'):
        commit_stored_pki_certificates(store, _snapshot(DAY - timedelta(hours=1)))
    with pytest.raises(ValueError, match='immutable'):
        commit_stored_pki_certificates(store, _snapshot(DAY + timedelta(minutes=1), fingerprint='b' * 64))
    assert PKIStoredCertificateObservation.query.one().fingerprint_sha256 == 'a' * 64


def test_revoked_approved_mount_cannot_commit(store):
    commit_stored_pki_certificates(store, _snapshot())
    provider = VaultInstance.query.filter_by(integration_instance_id=store).one()
    provider.pki_mounts = []
    db.session.commit()
    with pytest.raises(ValueError, match='not eligible'):
        commit_stored_pki_certificates(store, _snapshot(DAY + timedelta(minutes=1)))
    assert stored_pki_certificate_readiness(instance=provider)['state'] == 'not_configured'
    assert PKIStoredCertificateObservation.query.count() == 1


def test_failure_marks_only_stored_source_stale_not_vault_health(store):
    commit_stored_pki_certificates(store, _snapshot())
    previous = PKIStoredCertificateCollectionState.query.one().last_committed_at
    mark_stored_pki_certificates_failed(store, 'pki')
    state = PKIStoredCertificateCollectionState.query.one()
    assert state.last_committed_at == previous
    assert state.observed_stored_certificate_count == 1
    assert state.status == 'stale'
    assert (
        stored_pki_certificate_readiness(
            instance=VaultInstance.query.filter_by(integration_instance_id=store).one(),
        )['state']
        == 'stale'
    )
    assert db.session.get(IntegrationInstance, store).readiness_status == 'ready'


def test_provider_validation_is_separate_from_stored_cert_readiness(store):
    commit_stored_pki_certificates(store, _snapshot())
    identity = db.session.get(IntegrationInstance, store)
    identity.readiness_status = 'validation_required'
    db.session.commit()
    assert (
        stored_pki_certificate_readiness(
            instance=VaultInstance.query.filter_by(integration_instance_id=store).one(),
        )['state']
        == 'stale'
    )


def test_stored_cert_schema_excludes_raw_identity_and_key_material(store):
    for model in (PKIStoredCertificateObservation, PKIStoredCertificateCollectionState):
        names = {column.name for column in model.__table__.columns}
        assert not names.intersection(
            {
                'subject',
                'issuer',
                'dns_names',
                'san',
                'pem',
                'private_key',
                'client_token',
                'secret_id',
                'raw_provider_response',
                'provider_url',
            }
        )
    commit_stored_pki_certificates(store, _snapshot())
    stored = PKIStoredCertificateObservation.query.one()
    assert 'internal-private-tenant' not in repr(stored)
    assert 'private.example' not in repr(stored)


def test_nonqualified_coverage_or_duplicate_evidence_rejected(store):
    source = _snapshot()
    with pytest.raises(ValueError, match='unsupported'):
        commit_stored_pki_certificates(store, replace(source, coverage='all_issued'))
    with pytest.raises(ValueError, match='Duplicate'):
        commit_stored_pki_certificates(
            store,
            replace(source, certificates=source.certificates + source.certificates),
        )


def test_stored_cert_opt_in_revocation_blocks_collector_and_commit(store):
    provider = VaultInstance.query.filter_by(integration_instance_id=store).one()
    provider.pki_stored_certs_enabled = False
    db.session.commit()
    assert stored_pki_certificate_readiness(instance=provider)['state'] == 'not_configured'
    with pytest.raises(ValueError, match='not eligible'):
        commit_stored_pki_certificates(store, _snapshot())
    assert PKIStoredCertificateObservation.query.count() == 0
