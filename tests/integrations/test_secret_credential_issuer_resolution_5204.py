"""Read-only issuer candidate shape and latest-history selection (#5204)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.integration import IntegrationInstance
from app.models.secrets_pki import SecretCredentialIssuerRevision
from app.secrets_pki.credential_issuer_resolution import (
    IssuerResolutionTarget,
    _latest_issuer,
    issuer_candidate_key,
)

_NOW = datetime(2026, 11, 26, 3, tzinfo=UTC)
_PUBLIC = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
_TARGET = IssuerResolutionTarget(1, 'openbao', '', 'kv', 'a' * 64, 2)


def _source():
    return IntegrationInstance(
        id=1,
        name='fixture',
        integration_type='secrets_pki',
        provider_key='openbao',
        adapter_key='openbao',
        enabled=True,
        lifecycle_status='active',
        readiness_status='ready',
    )


def _record():
    return SecretCredentialIssuerRevision(
        integration_instance_id=1,
        provider_key='openbao',
        provider_namespace='',
        mount='kv',
        revision_number=2,
        lifecycle_status='active',
        algorithm='ed25519',
        public_key_hex=_PUBLIC.hex(),
        key_sha256=sha256(_PUBLIC).hexdigest(),
        deployment_ref='a' * 64,
        evidence_ref='b' * 64,
        requested_by_user_id=1,
        approved_by_user_id=2,
        approved_at=_NOW - timedelta(minutes=2),
        effective_from=_NOW - timedelta(minutes=1),
        effective_until=_NOW + timedelta(hours=1),
        recorded_by_user_id=2,
        recorded_at=_NOW - timedelta(minutes=1),
    )


def test_candidate_public_key_is_resolved_from_record():
    key = issuer_candidate_key(target=_TARGET, source=_source(), latest=_record(), now=_NOW)
    assert key is not None
    assert key.public_bytes_raw() == _PUBLIC


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('provider_key', 'vault'),
        ('integration_instance_id', 2),
        ('provider_namespace', 'other'),
        ('mount', 'other'),
        ('deployment_ref', 'c' * 64),
        ('revision_number', 3),
        ('lifecycle_status', 'revoked'),
        ('lifecycle_status', 'draft'),
        ('algorithm', 'rsa'),
        ('key_sha256', 'c' * 64),
        ('public_key_hex', 'Z' * 64),
        ('evidence_ref', ''),
        ('approved_by_user_id', 1),
        ('approved_at', None),
        ('recorded_by_user_id', 1),
        ('recorded_at', _NOW + timedelta(seconds=1)),
        ('effective_until', _NOW),
        ('effective_from', _NOW + timedelta(seconds=1)),
    ],
)
def test_changed_or_unqualified_latest_candidate_denied(field, value):
    record = _record()
    setattr(record, field, value)
    assert issuer_candidate_key(target=_TARGET, source=_source(), latest=record, now=_NOW) is None


@pytest.mark.parametrize(
    ('field', 'value'),
    [('provider_key', 'vault'), ('enabled', False), ('lifecycle_status', 'retired'), ('readiness_status', 'unknown')],
)
def test_source_drift_denied(field, value):
    source = _source()
    setattr(source, field, value)
    assert issuer_candidate_key(target=_TARGET, source=source, latest=_record(), now=_NOW) is None


def test_invalid_target_and_clock_denied():
    for target in (
        replace(_TARGET, integration_instance_id=True),
        replace(_TARGET, mount='*'),
        replace(_TARGET, provider_namespace='+'),
        replace(_TARGET, deployment_ref='invalid'),
        replace(_TARGET, revision_number=0),
    ):
        assert issuer_candidate_key(target=target, source=_source(), latest=_record(), now=_NOW) is None
    assert (
        issuer_candidate_key(target=_TARGET, source=_source(), latest=_record(), now=_NOW.replace(tzinfo=None)) is None
    )


@pytest.mark.parametrize('state', ['draft', 'revoked', 'active'])
def test_latest_query_never_filters_to_old_active_revision(state):
    engine = create_engine('sqlite://')
    try:
        IntegrationInstance.__table__.create(engine)
        SecretCredentialIssuerRevision.__table__.create(engine)
        with Session(engine) as session:
            session.add(_source())
            session.add(_record())
            newer = _record()
            newer.revision_number = 3
            newer.lifecycle_status = state
            newer.deployment_ref = 'c' * 64
            newer.provider_key = 'vault'
            session.add(newer)
            session.commit()
        with Session(engine, autoflush=False) as session:
            result = _latest_issuer(session, _TARGET)
            assert result is not None
            latest, source = result
            assert latest.revision_number == 3
            assert latest.lifecycle_status == state
            assert issuer_candidate_key(target=_TARGET, source=source, latest=latest, now=_NOW) is None
    finally:
        engine.dispose()


def test_connected_degraded_openbao_is_only_a_candidate_not_custody_authority():
    source = _source()
    source.readiness_status = 'degraded'
    source.health_status = 'connected'
    assert issuer_candidate_key(target=_TARGET, source=source, latest=_record(), now=_NOW) is not None
    source.health_status = 'disconnected'
    assert issuer_candidate_key(target=_TARGET, source=source, latest=_record(), now=_NOW) is None
