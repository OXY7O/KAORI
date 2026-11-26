"""Challenge storage constraints only; no operational single-use guarantee."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

from app.models.secrets_pki import SecretCredentialIssuerChallenge

_NOW = datetime(2026, 11, 26, 12, tzinfo=UTC)


def _pending():
    return {
        'integration_instance_id': 1,
        'provider_key': 'openbao',
        'provider_namespace': '',
        'mount': 'kv',
        'revision_number': 2,
        'deployment_ref': 'a' * 64,
        'key_sha256': 'b' * 64,
        'challenge_sha256': 'c' * 64,
        'source_owner_id': 1,
        'issued_at': _NOW,
        'expires_at': _NOW + timedelta(minutes=10),
        'lifecycle_status': 'pending',
    }


def _consumed():
    return {
        **_pending(),
        'lifecycle_status': 'consumed',
        'resolved_at': _NOW + timedelta(minutes=1),
        'resolved_by_user_id': 2,
        'possession_evidence_ref': 'd' * 64,
    }


@pytest.fixture
def challenge_table():
    engine = create_engine('sqlite://')
    table = SecretCredentialIssuerChallenge.__table__
    try:
        with engine.begin() as connection:
            # Isolated CHECK/unique tests; PostgreSQL FK and locking are separate.
            table.create(connection)
            yield connection, table
    finally:
        engine.dispose()


@pytest.mark.parametrize('provider_key', ['openbao', 'vault'])
def test_storage_accepts_pending_and_terminal_shapes(challenge_table, provider_key):
    connection, table = challenge_table
    connection.execute(table.insert().values(**{**_pending(), 'provider_key': provider_key}))
    connection.execute(
        table.insert().values(**{**_consumed(), 'provider_key': provider_key, 'challenge_sha256': 'e' * 64})
    )
    revoked = {
        **_pending(),
        'provider_key': provider_key,
        'challenge_sha256': 'f' * 64,
        'lifecycle_status': 'revoked',
        'resolved_at': _NOW + timedelta(hours=1),
        'resolved_by_user_id': 1,
    }
    connection.execute(table.insert().values(**revoked))


@pytest.mark.parametrize(
    'changes',
    [
        {'provider_key': 'unsupported'},
        {'provider_namespace': '*'},
        {'provider_namespace': '+'},
        {'mount': ''},
        {'mount': 'kv/*'},
        {'mount': 'kv/+'},
        {'revision_number': 0},
        {'deployment_ref': ''},
        {'key_sha256': 'b' * 63},
        {'challenge_sha256': ''},
        {'expires_at': _NOW},
        {'lifecycle_status': 'expired'},
        {'resolved_at': _NOW},
        {'resolved_by_user_id': 2},
        {'possession_evidence_ref': 'd' * 64},
    ],
)
def test_pending_invalid_shape_denied(challenge_table, changes):
    connection, table = challenge_table
    with pytest.raises(IntegrityError):
        connection.execute(table.insert().values(**(_pending() | changes)))


@pytest.mark.parametrize(
    'changes',
    [
        {'resolved_at': None},
        {'resolved_by_user_id': None},
        {'resolved_by_user_id': 1},
        {'resolved_at': _NOW - timedelta(seconds=1)},
        {'resolved_at': _NOW + timedelta(minutes=10)},
        {'possession_evidence_ref': None},
        {'possession_evidence_ref': ''},
        {'lifecycle_status': 'revoked'},
    ],
)
def test_consumed_invalid_shape_denied(challenge_table, changes):
    connection, table = challenge_table
    with pytest.raises(IntegrityError):
        connection.execute(table.insert().values(**(_consumed() | changes)))


def test_challenge_digest_unique_across_scopes_and_providers(challenge_table):
    connection, table = challenge_table
    connection.execute(table.insert().values(**_pending()))
    with pytest.raises(IntegrityError):
        connection.execute(
            table.insert().values(
                **{**_pending(), 'integration_instance_id': 2, 'provider_key': 'vault', 'mount': 'other'}
            )
        )
