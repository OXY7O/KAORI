"""Vault public PKI issuer commits are immutable, bounded and credential-free."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from flask import Flask

from app.extensions.db import db
from app.integrations.secrets_management.secrets_pki.commit_pki import (
    commit_pki_public_issuers,
    mark_pki_public_issuers_failed,
)
from app.integrations.secrets_management.secrets_pki.providers.vault.pki_public_evidence import (
    PKIIssuerCollection,
    PKIIssuerEvidence,
    PublicCertificateEvidence,
    parse_approved_pki_mounts,
)
from app.models.integration import IntegrationInstance
from app.models.secrets_pki_pki import (
    PKIIssuerCollectionState,
    PKIIssuerIdentity,
    PKIPublicCertificateObservation,
)
from app.models.vault import VaultInstance

ISSUER_UUID = '1ae8ce9d-2f70-0761-a465-8c9840a247a2'
DAY = datetime(2026, 10, 22, tzinfo=UTC)


@pytest.fixture
def store():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY='local-only-test',
        SQLALCHEMY_DATABASE_URI='sqlite://',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        INTEGRATION_CREDENTIAL_KEY=Fernet.generate_key().decode('ascii'),
    )
    db.init_app(app)
    with app.app_context():
        tables = [
            IntegrationInstance.__table__,
            VaultInstance.__table__,
            PKIIssuerIdentity.__table__,
            PKIPublicCertificateObservation.__table__,
            PKIIssuerCollectionState.__table__,
        ]
        db.Model.metadata.create_all(bind=db.engine, tables=tables)
        identity = IntegrationInstance(
            integration_type='secrets_pki',
            provider_key='vault',
            adapter_key='vault_http_v1',
            name='pki-test',
            environment='testing',
            enabled=True,
            readiness_status='ready',
        )
        db.session.add(identity)
        db.session.flush()
        db.session.add(
            VaultInstance(
                integration_instance_id=identity.id,
                endpoint='https://vault.test.invalid',
                auth_mount='approle',
                role_id='readonly',
                secret_id='not-retained',
                timeout=5,
                verify_ssl=True,
                pki_mounts=['pki'],
            )
        )
        db.session.commit()
        try:
            yield identity.id
        finally:
            db.session.remove()
            db.Model.metadata.drop_all(bind=db.engine, tables=list(reversed(tables)))


def _snapshot(at=DAY, *, fingerprint='a' * 64, issuer_id=ISSUER_UUID, complete=True, empty=False):
    cert = PublicCertificateEvidence(
        fingerprint_sha256=fingerprint,
        serial_hex='123abc',
        subject='CN=Internal Issuer May Be Sensitive',
        issuer='CN=Sensitive Root',
        valid_from=DAY - timedelta(days=2),
        valid_until=DAY + timedelta(days=365),
        is_ca=True,
        self_issued=False,
        dns_names=('private.domain.invalid',),
    )
    record = PKIIssuerEvidence(
        issuer_id=issuer_id,
        issuer_name='sensitive-issuer-label',
        certificate=cert,
        chain_fingerprints=('b' * 64,),
    )
    return PKIIssuerCollection(
        mount='pki',
        observed_at=at,
        issuers=() if empty else (record,),
        complete=complete,
    )


def test_committed_public_certificate_history_uses_stable_local_issuer_identity(store):
    initial = commit_pki_public_issuers(store, _snapshot())
    assert initial.observed_issuer_count == 1
    assert initial.observed_certificate_count == 1
    issuer = PKIIssuerIdentity.query.one()
    local_id = issuer.id

    commit_pki_public_issuers(store, _snapshot(DAY + timedelta(minutes=2), fingerprint='c' * 64))
    assert PKIIssuerIdentity.query.count() == 1
    assert PKIIssuerIdentity.query.one().id == local_id
    certs = {c.fingerprint_sha256: c.observation_status for c in PKIPublicCertificateObservation.query.all()}
    assert certs == {'a' * 64: 'historical', 'c' * 64: 'observed'}
    assert PKIIssuerCollectionState.query.one().observed_issuer_count == 1


def test_public_evidence_never_persists_subject_san_pem_issuer_label_or_secrets(store):
    commit_pki_public_issuers(store, _snapshot())
    for model in (PKIIssuerIdentity, PKIPublicCertificateObservation, PKIIssuerCollectionState):
        columns = {col.name for col in model.__table__.columns}
        assert not columns.intersection(
            {
                'subject',
                'issuer_name',
                'san',
                'dns_names',
                'private_key',
                'pem',
                'client_token',
                'secret_id',
                'raw_response',
            }
        )
    data = repr(
        [
            (c.fingerprint_sha256, c.serial_hex, c.chain_fingerprints)
            for c in PKIPublicCertificateObservation.query.all()
        ]
    )
    for sensitive in ('Sensitive', 'sensitive-issuer-label', 'private.domain.invalid', 'not-retained'):
        assert sensitive not in data


def test_empty_after_nonempty_and_partial_source_cannot_erase_issuer_history(store):
    commit_pki_public_issuers(store, _snapshot())
    with pytest.raises(ValueError, match='empty'):
        commit_pki_public_issuers(store, _snapshot(DAY + timedelta(minutes=1), empty=True))
    with pytest.raises(ValueError, match='incomplete'):
        commit_pki_public_issuers(store, _snapshot(DAY + timedelta(minutes=1), complete=False))
    assert PKIIssuerIdentity.query.one().observation_status == 'observed'
    assert PKIIssuerCollectionState.query.one().observed_issuer_count == 1


def test_unseen_issuer_is_unknown_not_revoked_or_deleted(store):
    commit_pki_public_issuers(store, _snapshot())
    newer = replace(
        _snapshot(DAY + timedelta(minutes=3)),
        issuers=(replace(_snapshot().issuers[0], issuer_id='40e903ae-9b5c-4ca0-890e-6b4f0ac4ea66'),),
    )
    summary = commit_pki_public_issuers(store, newer)
    assert summary.not_observed_issuer_count == 1
    previous = PKIIssuerIdentity.query.filter_by(provider_issuer_id=ISSUER_UUID).one()
    assert previous.observation_status == 'not_observed'
    assert {cert.observation_status for cert in previous.certificates} == {'not_observed'}
    assert PKIPublicCertificateObservation.query.count() == 2


def test_revoked_mount_disables_new_commit_without_mutating_prior_evidence(store):
    commit_pki_public_issuers(store, _snapshot())
    instance = VaultInstance.query.filter_by(integration_instance_id=store).one()
    instance.pki_mounts = []
    db.session.commit()
    with pytest.raises(ValueError, match='not eligible'):
        commit_pki_public_issuers(store, _snapshot(DAY + timedelta(minutes=1)))
    assert PKIIssuerIdentity.query.count() == 1
    assert PKIIssuerCollectionState.query.one().status == 'ready'


def test_failed_collection_marks_scope_stale_and_preserves_committed_history(store):
    commit_pki_public_issuers(store, _snapshot())
    committed = PKIIssuerCollectionState.query.one().last_committed_at
    mark_pki_public_issuers_failed(store, 'pki')
    state = PKIIssuerCollectionState.query.one()
    assert state.status == 'stale'
    assert state.last_committed_at == committed
    assert state.observed_issuer_count == 1
    assert 'Sensitive' not in (state.last_error or '')
    assert PKIPublicCertificateObservation.query.count() == 1


def test_out_of_order_or_conflicting_fingerprint_observations_fail_closed(store):
    commit_pki_public_issuers(store, _snapshot())
    with pytest.raises(ValueError, match='Out-of-order'):
        commit_pki_public_issuers(store, _snapshot(DAY - timedelta(days=1)))
    current = _snapshot(DAY + timedelta(minutes=3))
    edited_cert = replace(current.issuers[0].certificate, serial_hex='456def')
    modified = replace(current, issuers=(replace(current.issuers[0], certificate=edited_cert),))
    with pytest.raises(ValueError, match='Immutable'):
        commit_pki_public_issuers(store, modified)
    assert PKIPublicCertificateObservation.query.one().serial_hex == '123abc'


@pytest.mark.parametrize(
    'configured',
    [
        'pki/../secret',
        'pki,',
        'pki,pki',
        'pki%2fhidden',
        'a,b,c,d,e',
        ' pki/',
        '../pki',
    ],
)
def test_invalid_or_overbroad_pki_mount_scope_is_rejected(configured):
    with pytest.raises(ValueError):
        parse_approved_pki_mounts(configured)


def test_pki_readiness_uses_only_committed_state_and_honest_zero(store):
    from app.secrets_pki.pki_presentation import pki_public_readiness

    instance = VaultInstance.query.filter_by(integration_instance_id=store).one()
    missing = pki_public_readiness(instance=instance)
    assert missing['state'] == 'not_collected'
    assert missing['observed_issuers'] is None

    commit_pki_public_issuers(store, _snapshot(datetime.now(UTC), empty=True))
    committed_zero = pki_public_readiness(instance=instance)
    assert committed_zero['state'] == 'committed'
    assert committed_zero['observed_issuers'] == 0
    assert committed_zero['committed_mounts'] == 1

    mark_pki_public_issuers_failed(store, 'pki')
    stale = pki_public_readiness(instance=instance)
    assert stale['state'] == 'stale'
    assert stale['observed_issuers'] == 0

    instance.pki_mounts = []
    db.session.commit()
    disabled = pki_public_readiness(instance=instance)
    assert disabled['state'] == 'not_configured'
    assert disabled['observed_issuers'] is None


def test_provider_reconfiguration_rejects_ready_pki_badge_until_validation(store):
    from app.secrets_pki.pki_presentation import pki_public_readiness

    commit_pki_public_issuers(store, _snapshot(datetime.now(UTC)))
    vault = VaultInstance.query.filter_by(integration_instance_id=store).one()
    identity = db.session.get(IntegrationInstance, store)
    identity.readiness_status = 'validation_required'
    db.session.commit()
    readiness = pki_public_readiness(instance=vault)
    assert readiness['state'] == 'stale'
    assert readiness['observed_issuers'] == 1
    with pytest.raises(ValueError, match='not eligible'):
        commit_pki_public_issuers(store, _snapshot(DAY + timedelta(minutes=1)))
