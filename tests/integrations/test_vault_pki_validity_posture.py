"""Vault stored-certificate validity is not a trust/delivery/revocation verdict."""

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from flask import Flask

from app.extensions.db import db
from app.models.integration import IntegrationInstance
from app.models.secrets_pki_stored_certificates import (
    PKIStoredCertificateCollectionState,
    PKIStoredCertificateObservation,
)
from app.models.vault import VaultInstance
from app.secrets_pki.pki_validity_posture import build_stored_pki_validity_posture

AT = datetime(2026, 10, 22, 12, tzinfo=UTC)


@pytest.fixture
def stored_cert_source():
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
            PKIStoredCertificateCollectionState.__table__,
            PKIStoredCertificateObservation.__table__,
        ]
        db.Model.metadata.create_all(bind=db.engine, tables=tables)
        provider = IntegrationInstance(
            integration_type='secrets_pki',
            provider_key='vault',
            adapter_key='vault_http_v1',
            name='private-issuer-name',
            environment='testing',
            enabled=True,
            lifecycle_status='active',
            readiness_status='ready',
        )
        db.session.add(provider)
        db.session.flush()
        db.session.add_all(
            [
                VaultInstance(
                    integration_instance_id=provider.id,
                    endpoint='https://vault.invalid',
                    auth_mount='approle',
                    role_id='fixture',
                    secret_id='test-secret-id',
                    timeout=5,
                    verify_ssl=True,
                    pki_mounts=['pki'],
                    pki_stored_certs_enabled=True,
                ),
                PKIStoredCertificateCollectionState(
                    integration_instance_id=provider.id,
                    provider_namespace='',
                    mount='pki',
                    status='ready',
                    observed_stored_certificate_count=0,
                    last_observed_at=AT,
                    last_committed_at=AT,
                ),
            ]
        )
        db.session.commit()
        try:
            yield provider.id
        finally:
            db.session.remove()
            db.Model.metadata.drop_all(bind=db.engine, tables=list(reversed(tables)))


def _read():
    return build_stored_pki_validity_posture(now=AT + timedelta(minutes=5))


def _add_cert(provider_id, *, valid_from, valid_until, observation=AT, current=True):
    state = PKIStoredCertificateCollectionState.query.filter_by(
        integration_instance_id=provider_id,
    ).one()
    number = PKIStoredCertificateObservation.query.count() + 1
    db.session.add(
        PKIStoredCertificateObservation(
            integration_instance_id=provider_id,
            provider_namespace='',
            mount='pki',
            serial_hex=format(number, 'x'),
            fingerprint_sha256=format(number, '064x'),
            valid_from=valid_from,
            valid_until=valid_until,
            observation_status='observed' if current else 'not_observed',
            last_observed_at=observation,
        )
    )
    if current:
        state.observed_stored_certificate_count += 1
    db.session.commit()


def test_committed_empty_is_zero_but_not_comprehensive_issuance(stored_cert_source):
    result = _read()
    assert result['status'] == 'ready'
    assert result['observed_stored_certificates'] == 0
    assert result['within_validity_window'] == 0
    assert not result['trust_verified']
    assert not result['revocation_verified']
    assert not result['endpoint_serving_verified']


@pytest.mark.parametrize(
    ('offset_before', 'offset_after', 'expected'),
    [
        (-10, 20, 'within_validity_window'),
        (10, 20, 'not_yet_valid'),
        (-20, -10, 'expired'),
        (20, -10, 'unknown'),
    ],
)
def test_public_validity_window_classified_without_claiming_trust(
    stored_cert_source,
    offset_before,
    offset_after,
    expected,
):
    _add_cert(
        stored_cert_source,
        valid_from=AT + timedelta(days=offset_before),
        valid_until=AT + timedelta(days=offset_after),
    )
    result = _read()
    assert result['status'] == 'ready'
    assert result[expected] == 1
    assert result['observed_stored_certificates'] == 1
    assert 'private-issuer-name' not in repr(result)
    assert 'test-secret-id' not in repr(result)
    assert 'serial_hex' not in result and 'fingerprint_sha256' not in result
    assert not result['trust_verified'] and not result['endpoint_serving_verified']


def test_missing_or_failed_generation_has_no_fabricated_zero(stored_cert_source):
    state = PKIStoredCertificateCollectionState.query.one()
    state.status = 'failed'
    db.session.commit()
    result = _read()
    assert result['status'] == 'incomplete'
    assert result['observed_stored_certificates'] is None
    state.status = 'ready'
    state.last_committed_at = AT - timedelta(days=2)
    db.session.commit()
    assert _read()['within_validity_window'] is None


def test_optout_revokes_live_aggregate_coverage_without_erasing_history(stored_cert_source):
    _add_cert(
        stored_cert_source,
        valid_from=AT - timedelta(days=2),
        valid_until=AT + timedelta(days=90),
    )
    instance = VaultInstance.query.filter_by(integration_instance_id=stored_cert_source).one()
    instance.pki_stored_certs_enabled = False
    db.session.commit()
    result = _read()
    assert result['status'] == 'not_configured'
    assert result['observed_stored_certificates'] is None
    assert PKIStoredCertificateObservation.query.count() == 1


def test_unvalidated_source_and_removed_mount_are_unqualified(stored_cert_source):
    _add_cert(
        stored_cert_source,
        valid_from=AT - timedelta(days=2),
        valid_until=AT + timedelta(days=90),
    )
    provider = db.session.get(IntegrationInstance, stored_cert_source)
    provider.readiness_status = 'stale'
    db.session.commit()
    assert _read()['status'] == 'unavailable'
    provider.readiness_status = 'ready'
    vault = VaultInstance.query.filter_by(integration_instance_id=stored_cert_source).one()
    vault.pki_mounts = []
    db.session.commit()
    assert _read()['status'] == 'not_configured'


def test_collection_count_mismatch_blocks_all_expiration_counts(stored_cert_source):
    _add_cert(
        stored_cert_source,
        valid_from=AT - timedelta(days=2),
        valid_until=AT + timedelta(days=90),
    )
    state = PKIStoredCertificateCollectionState.query.one()
    state.observed_stored_certificate_count = 2
    db.session.commit()
    result = _read()
    assert result['status'] == 'incomplete'
    assert result['expired'] is None


def test_historical_cert_not_current_and_zero_only_with_fresh_empty_generation(stored_cert_source):
    _add_cert(
        stored_cert_source,
        valid_from=AT - timedelta(days=100),
        valid_until=AT - timedelta(days=50),
        current=False,
    )
    result = _read()
    assert result['observed_stored_certificates'] == 0
    assert result['expired'] == 0


def test_old_row_generation_not_current_public_validity(stored_cert_source):
    _add_cert(
        stored_cert_source,
        valid_from=AT - timedelta(days=2),
        valid_until=AT + timedelta(days=90),
        observation=AT - timedelta(days=1),
    )
    result = _read()
    assert result['status'] == 'incomplete'
    assert result['observed_stored_certificates'] is None


def test_overbound_observed_count_is_never_partial_healthy(stored_cert_source):
    state = PKIStoredCertificateCollectionState.query.one()
    state.observed_stored_certificate_count = 65
    db.session.commit()
    assert _read()['status'] == 'incomplete'


@pytest.mark.parametrize(
    ('days_until_expiry', 'expected'),
    [
        (1, 'expires_within_7d'),
        (7, 'expires_within_7d'),
        (8, 'expires_8_to_30d'),
        (30, 'expires_8_to_30d'),
        (31, 'expires_after_30d'),
    ],
)
def test_exclusive_pki_expiry_horizons_are_computed_from_qualified_public_metadata(
    stored_cert_source,
    days_until_expiry,
    expected,
):
    instant = AT + timedelta(minutes=5)
    _add_cert(
        stored_cert_source,
        valid_from=AT - timedelta(days=1),
        valid_until=instant + timedelta(days=days_until_expiry),
    )
    result = _read()
    assert result['status'] == 'ready'
    assert result[expected] == 1
    assert (
        sum(
            result[band]
            for band in (
                'expires_within_7d',
                'expires_8_to_30d',
                'expires_after_30d',
            )
        )
        == result['within_validity_window']
        == 1
    )
    assert result['last_observed_at'] is not None
    assert 'private-issuer-name' not in repr(result)
    assert 'test-secret-id' not in repr(result)
    assert 'serial_hex' not in repr(result)
    assert 'fingerprint_sha256' not in repr(result)


def test_unqualified_pki_never_exposes_expiration_band_zeros(stored_cert_source):
    state = PKIStoredCertificateCollectionState.query.one()
    state.status = 'failed'
    db.session.commit()
    result = _read()
    assert result['status'] == 'incomplete'
    assert result['last_observed_at'] is None
    assert all(
        result[band] is None
        for band in (
            'expires_within_7d',
            'expires_8_to_30d',
            'expires_after_30d',
        )
    )


def test_not_yet_valid_and_expired_never_counted_as_upcoming(stored_cert_source):
    _add_cert(
        stored_cert_source,
        valid_from=AT + timedelta(days=1),
        valid_until=AT + timedelta(days=7),
    )
    _add_cert(
        stored_cert_source,
        valid_from=AT - timedelta(days=7),
        valid_until=AT - timedelta(days=1),
    )
    result = _read()
    assert result['not_yet_valid'] == 1
    assert result['expired'] == 1
    assert (
        sum(
            result[band]
            for band in (
                'expires_within_7d',
                'expires_8_to_30d',
                'expires_after_30d',
            )
        )
        == 0
    )


def test_exact_expiry_instant_is_expired_not_upcoming(stored_cert_source):
    instant = AT + timedelta(minutes=5)
    _add_cert(
        stored_cert_source,
        valid_from=AT - timedelta(days=1),
        valid_until=instant,
    )
    result = _read()
    assert result['status'] == 'ready'
    assert result['expired'] == 1
    assert result['expires_within_7d'] == 0
    assert result['expires_8_to_30d'] == 0
    assert result['expires_after_30d'] == 0
