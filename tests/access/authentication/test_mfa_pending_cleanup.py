"""Maintenance removes only invalid pending material, with committed evidence (#5381)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.access.authentication.identity_provider.adapters.ldap.reauthentication import (
    LdapReauthenticationProof,
    ldap_binding_fingerprint,
)
from app.access.authentication.mfa import cleanup
from app.access.authentication.results import ExternalCredentialProof
from app.models.notification import Notification
from app.security import credentials

NOW = datetime(2026, 11, 28, tzinfo=UTC)
ACCOUNT = cleanup.AccountMetadata(42, 7, 'database', None, True, None)
PENDING = cleanup.PendingMetadata(1, 42, False, 7, True, NOW + timedelta(minutes=1), None, None, None, False)


@pytest.mark.parametrize(
    ('factor', 'reason'),
    [
        (PENDING, None),
        (replace(PENDING, enrollment_expires_at=NOW), 'expired'),
        (replace(PENDING, enrollment_expires_at=None), 'expired'),
        (replace(PENDING, enrollment_generation=6), 'invalid_owner'),
        (replace(PENDING, enrollment_authenticated=None), 'invalid_owner'),
        (replace(PENDING, enrollment_generation=None), 'invalid_owner'),
    ],
)
def test_inactive_enrollment_boundary(factor: cleanup.PendingMetadata, reason: str | None) -> None:
    expected = ('enrollment', reason) if reason is not None else None
    assert cleanup.invalid_pending_material(ACCOUNT, factor, now=NOW) == expected


@pytest.mark.parametrize(
    ('factor', 'reason'),
    [
        (replace(PENDING, enabled=True), None),
        (replace(PENDING, enabled=True, replacement_seed_present=True), 'invalid_owner'),
        (
            replace(PENDING, enabled=True, replacement_seed_present=True, replacement_generation=7,
                    replacement_expires_at=NOW),
            'expired',
        ),
        (
            replace(PENDING, enabled=True, replacement_seed_present=True, replacement_generation=7,
                    replacement_expires_at=NOW + timedelta(minutes=1)),
            None,
        ),
        (
            replace(PENDING, enabled=True, replacement_seed_present=True, replacement_generation=7,
                    replacement_expires_at=NOW + timedelta(minutes=1), replacement_provider_proof={}),
            'invalid_provider_proof',
        ),
    ],
)
def test_enabled_factor_only_classifies_replacement(factor: cleanup.PendingMetadata, reason: str | None) -> None:
    expected = ('replacement', reason) if reason is not None else None
    assert cleanup.invalid_pending_material(ACCOUNT, factor, now=NOW) == expected


@pytest.mark.parametrize('condition', ('valid', 'stale_revision', 'wrong_link', 'wrong_dn', 'ambiguous', 'disabled'))
def test_ldap_proof_cleanup_reads_only_committed_binding(
    condition: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = replace(ACCOUNT, source='ldap_directory', subject='stable')
    proof = LdapReauthenticationProof(
        ExternalCredentialProof(7, 3, 11), 'stable', ldap_binding_fingerprint('stable', 'cn=fixture'), NOW
    )
    factor = replace(
        PENDING,
        enabled=True,
        replacement_seed_present=True,
        replacement_generation=7,
        replacement_expires_at=NOW + timedelta(minutes=1),
        replacement_provider_proof=proof.to_record(),
    )
    row = (
        12 if condition == 'wrong_link' else 11,
        7,
        'stable',
        'cn=changed' if condition == 'wrong_dn' else 'cn=fixture',
        4 if condition == 'stale_revision' else 3,
        condition != 'disabled',
        'ldap',
    )
    store = Mock()
    store.execute.return_value.all.return_value = [row, row] if condition == 'ambiguous' else [row]
    monkeypatch.setattr(cleanup, 'db', SimpleNamespace(session=store))
    expected = None if condition == 'valid' else ('replacement', 'invalid_provider_proof')
    assert cleanup.invalid_pending_material(account, factor, now=NOW) == expected
    sql = str(store.execute.call_args.args[0]).lower()
    assert 'for update' not in sql
    assert 'configuration_json' not in sql


@pytest.mark.parametrize('execute', (False, True))
def test_bounded_page_rechecks_metadata_and_skips_contended_rows(
    execute: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = Mock()
    store.execute.return_value.all.return_value = [(1, 42), (2, 43), (3, 44)]
    account = Mock(side_effect=[ACCOUNT, None])
    factor = Mock(return_value=replace(PENDING, enrollment_expires_at=NOW))
    apply = Mock()
    event = Mock(return_value=object())
    monkeypatch.setattr(cleanup, 'db', SimpleNamespace(session=store))
    monkeypatch.setattr(cleanup, '_account_metadata', account)
    monkeypatch.setattr(cleanup, '_factor_metadata', factor)
    monkeypatch.setattr(cleanup, '_apply_cleanup', apply)
    monkeypatch.setattr(cleanup, 'stage_pending_mfa_cleanup_event', event)
    result = cleanup.cleanup_pending_mfa(execute=execute, limit=2)
    assert result['examined'] == 2
    assert result['skipped_or_missing'] == 1
    assert result['next_after_id'] == 2
    assert result['eligible_enrollment'] == 1
    assert account.call_args_list[0].kwargs['lock'] is execute
    assert factor.call_args.kwargs['lock'] is execute
    assert result['removed_enrollment'] == int(execute)
    if execute:
        apply.assert_called_once()
        event.assert_called_once()
        store.commit.assert_called_once()
    else:
        apply.assert_not_called()
        event.assert_not_called()
        store.commit.assert_not_called()
        store.rollback.assert_called_once()


@pytest.mark.parametrize('failure', (False, True))
def test_database_cleanup_is_secret_free_atomic_and_idempotent(
    failure: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    # SQLite verifies actual DML/rollback and projection, not PostgreSQL locking.
    engine = sa.create_engine('sqlite+pysqlite:///:memory:')
    with engine.connect() as connection:
        connection.execute(sa.text(
            'CREATE TABLE users (id INTEGER PRIMARY KEY, auth_session_version BIGINT, auth_source TEXT, '
            'external_id TEXT, account_is_active BOOLEAN, deleted_at DATETIME)'
        ))
        connection.execute(sa.text(
            'CREATE TABLE authentication_mfa_factors (id INTEGER PRIMARY KEY, user_id INTEGER, '
            'totp_secret TEXT, enabled BOOLEAN, recovery_hashes JSON, last_accepted_step BIGINT, '
            'enrollment_generation BIGINT, enrollment_authenticated BOOLEAN, enrollment_expires_at DATETIME, '
            'replacement_totp_secret TEXT, replacement_generation BIGINT, replacement_expires_at DATETIME, '
            'replacement_provider_proof JSON, updated_at DATETIME)'
        ))
        Notification.__table__.create(connection)
        connection.execute(sa.text(
            "INSERT INTO users VALUES (42, 7, 'database', NULL, true, NULL), "
            "(43, 7, 'database', NULL, true, NULL), (44, 7, 'database', NULL, true, NULL)"
        ))
        connection.execute(sa.text(
            "INSERT INTO authentication_mfa_factors VALUES "
            "(1, 42, 'opaque-inactive', false, '[]', NULL, 7, true, '2000-01-01', NULL, NULL, NULL, NULL, NULL), "
            "(2, 43, 'opaque-active', true, '[\"preserved-hash\"]', 42, NULL, NULL, NULL, "
            "'opaque-pending', 7, '2000-01-01', NULL, NULL), "
            "(3, 44, 'opaque-valid', false, '[]', NULL, 7, true, '2999-01-01', NULL, NULL, NULL, NULL, NULL)"
        ))
        connection.commit()
        with Session(bind=connection) as store:
            monkeypatch.setattr(cleanup, 'db', SimpleNamespace(session=store))
            decrypt = Mock(side_effect=AssertionError('Maintenance must not decrypt factor values.'))
            monkeypatch.setattr(credentials, 'decrypt_credential', decrypt)
            preview = cleanup.cleanup_pending_mfa()
            assert preview['eligible_enrollment'] == preview['eligible_replacement'] == 1
            assert preview['removed_enrollment'] == preview['cleared_replacement'] == 0
            if failure:
                monkeypatch.setattr(
                    cleanup, 'stage_pending_mfa_cleanup_event', Mock(side_effect=SQLAlchemyError('audit failure'))
                )
                with pytest.raises(SQLAlchemyError):
                    cleanup.cleanup_pending_mfa(execute=True)
            else:
                result = cleanup.cleanup_pending_mfa(execute=True)
                assert result['removed_enrollment'] == result['cleared_replacement'] == 1
                second = cleanup.cleanup_pending_mfa(execute=True)
                assert second['removed_enrollment'] == second['cleared_replacement'] == 0
            rows = store.execute(sa.text(
                'SELECT id, totp_secret, enabled, recovery_hashes, last_accepted_step, replacement_totp_secret '
                'FROM authentication_mfa_factors ORDER BY id'
            )).all()
            active = next(row for row in rows if row[0] == 2)
            assert tuple(active) == (2, 'opaque-active', 1, '["preserved-hash"]', 42,
                                     'opaque-pending' if failure else None)
            assert [row[0] for row in rows] == ([1, 2, 3] if failure else [2, 3])
            assert store.execute(sa.text('SELECT count(*) FROM notifications')).scalar_one() == (0 if failure else 2)
            assert store.execute(sa.text('SELECT auth_session_version FROM users ORDER BY id')).scalars().all() == [7, 7, 7]
            decrypt.assert_not_called()
    engine.dispose()
