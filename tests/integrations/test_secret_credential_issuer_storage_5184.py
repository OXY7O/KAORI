"""Exact-scope issuer storage constraints; no operational trust is asserted."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from app.models.secrets_pki import SecretCredentialIssuerRevision

_PUBLIC_KEY = bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')


def _record(now):
    return {
        'integration_instance_id': 1,
        'provider_key': 'vault',
        'provider_namespace': '',
        'mount': 'kv',
        'revision_number': 2,
        'lifecycle_status': 'active',
        'algorithm': 'ed25519',
        'public_key_hex': _PUBLIC_KEY.hex(),
        'key_sha256': sha256(_PUBLIC_KEY).hexdigest(),
        'deployment_ref': 'a' * 64,
        'evidence_ref': 'b' * 64,
        'requested_by_user_id': 1,
        'approved_by_user_id': 2,
        'approved_at': now,
        'effective_from': now,
        'effective_until': now + timedelta(hours=1),
        'recorded_by_user_id': 2,
        'recorded_at': now,
    }


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('revision_number', 0),
        ('provider_key', 'unsupported'),
        ('provider_namespace', '*'),
        ('mount', ''),
        ('mount', 'kv/*'),
        ('lifecycle_status', 'unknown'),
        ('algorithm', 'rsa'),
        ('public_key_hex', 'a' * 63),
        ('key_sha256', 'a' * 63),
        ('deployment_ref', ''),
        ('evidence_ref', ''),
        ('approved_by_user_id', None),
        ('approved_by_user_id', 1),
        ('approved_at', None),
        ('recorded_by_user_id', 1),
    ],
)
def test_issuer_revision_shape_constraints(field, value):
    engine = create_engine('sqlite://')
    table = SecretCredentialIssuerRevision.__table__
    values = _record(datetime.now(UTC))
    values[field] = value
    try:
        with engine.begin() as connection:
            # Isolated CHECK tests, not PostgreSQL FK/locking validation.
            table.create(connection)
            with pytest.raises(IntegrityError):
                connection.execute(table.insert().values(**values))
    finally:
        engine.dispose()


@pytest.mark.parametrize('provider_key', ['vault', 'openbao'])
def test_append_only_intended_history_unique_scope_revision(provider_key):
    engine = create_engine('sqlite://')
    table = SecretCredentialIssuerRevision.__table__
    now = datetime.now(UTC)
    values = {**_record(now), 'provider_key': provider_key}
    try:
        with engine.begin() as connection:
            table.create(connection)
            draft = {
                **values,
                'revision_number': 1,
                'lifecycle_status': 'draft',
                'approved_by_user_id': None,
                'approved_at': None,
                'recorded_by_user_id': 1,
            }
            connection.execute(table.insert().values(**draft))
            connection.execute(table.insert().values(**values))
            revoked = {
                **values,
                'revision_number': 3,
                'lifecycle_status': 'revoked',
                'recorded_at': now + timedelta(hours=2),
            }
            connection.execute(table.insert().values(**revoked))
            with pytest.raises(IntegrityError):
                connection.execute(table.insert().values(**values))
    finally:
        engine.dispose()


def test_invalid_issuer_window_denied():
    engine = create_engine('sqlite://')
    table = SecretCredentialIssuerRevision.__table__
    now = datetime.now(UTC)
    values = {**_record(now), 'effective_until': now}
    try:
        with engine.begin() as connection:
            table.create(connection)
            with pytest.raises(IntegrityError):
                connection.execute(table.insert().values(**values))
    finally:
        engine.dispose()
