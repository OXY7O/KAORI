"""SC-01 persisted source identity contract tests (#2740).

These use ephemeral SQLite tables only. No GitHub API, GitHub App credential,
running worker, or Dev Container provider installation is required.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, insert, select
from sqlalchemy.exc import IntegrityError

from app.models.integration import IntegrationInstance
from app.models.source_control import GitHubAppCredential
from app.models.source_control import (
    SourceAccount,
    SourceInstallation,
    SourceReference,
    SourceReferenceTransition,
    SourceRepository,
    SourceRepositoryGrant,
    SourceRevision,
)


@pytest.fixture
def source_engine():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    with engine.connect() as connection:
        connection.exec_driver_sql('PRAGMA foreign_keys = ON')
    tables = (
        IntegrationInstance.__table__,
        SourceAccount.__table__,
        GitHubAppCredential.__table__,
        SourceInstallation.__table__,
        SourceRepository.__table__,
        SourceRepositoryGrant.__table__,
        SourceRevision.__table__,
        SourceReference.__table__,
        SourceReferenceTransition.__table__,
    )
    IntegrationInstance.metadata.create_all(bind=engine, tables=list(tables))
    yield engine
    engine.dispose()


def _connection(connection, name: str) -> int:
    return connection.execute(
        insert(IntegrationInstance).values(
            name=name, integration_type='source_control', provider_key='github',
            adapter_key='github_rest_v3', enabled=False, readiness_status='validation_required',
        )
    ).inserted_primary_key[0]


def _account(connection, native_id: str, login: str = 'shared') -> int:
    return connection.execute(
        insert(SourceAccount).values(
            provider_key='github', host_key='github.com', native_account_id=native_id,
            account_type='organization', login=login,
        )
    ).inserted_primary_key[0]


def _repository(connection, account: int, native_id: str, name: str) -> int:
    return connection.execute(
        insert(SourceRepository).values(
            provider_key='github', host_key='github.com', native_repository_id=native_id,
            account_id=account, name=name, full_name=f'shared/{name}',
            provider_presence='observed', archived=False,
        )
    ).inserted_primary_key[0]


def _installation(connection, account: int, conn_id: int, app: str, install: str) -> int:
    return connection.execute(
        insert(SourceInstallation).values(
            integration_instance_id=conn_id, account_id=account,
            provider_key='github', host_key='github.com',
            native_app_id=app, native_installation_id=install,
            repository_scope='selected', grant_status='unknown',
        )
    ).inserted_primary_key[0]


def test_native_repository_identity_is_not_owner_name_or_installation(source_engine) -> None:
    with source_engine.begin() as connection:
        account = _account(connection, '42', login='old-owner')
        repository = _repository(connection, account, '99', 'service')
        first = _installation(connection, account, _connection(connection, 'gh-a'), '7', '111')
        second = _installation(connection, account, _connection(connection, 'gh-b'), '7', '222')
        observed = datetime(2026, 10, 23, tzinfo=UTC)
        for installation in (first, second):
            connection.execute(
                insert(SourceRepositoryGrant).values(
                    installation_id=installation, repository_id=repository,
                    access_status='granted', valid_from=observed, last_observed_at=observed,
                )
            )
        row = connection.execute(select(SourceRepository).where(SourceRepository.id == repository)).scalar_one()
        assert row.native_repository_id == '99'
        assert row.account_id == account
        grants = connection.execute(
            select(SourceRepositoryGrant.installation_id).where(
                SourceRepositoryGrant.repository_id == repository
            )
        ).scalars().all()
        assert sorted(grants) == sorted([first, second])


def test_duplicate_current_grant_is_rejected_but_history_is_retained(source_engine) -> None:
    with source_engine.begin() as connection:
        account = _account(connection, '3')
        repository = _repository(connection, account, '4', 'one')
        installation = _installation(connection, account, _connection(connection, 'gh'), '8', '9')
        start = datetime(2026, 10, 22, tzinfo=UTC)
        connection.execute(
            insert(SourceRepositoryGrant).values(
                installation_id=installation, repository_id=repository,
                access_status='granted', valid_from=start, last_observed_at=start,
            )
        )
        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(
                    insert(SourceRepositoryGrant).values(
                        installation_id=installation, repository_id=repository,
                        access_status='granted', valid_from=start + timedelta(hours=1),
                        last_observed_at=start + timedelta(hours=1),
                    )
                )
        connection.execute(
            SourceRepositoryGrant.__table__.update()
            .where(SourceRepositoryGrant.installation_id == installation)
            .values(valid_until=start + timedelta(hours=2))
        )
        connection.execute(
            insert(SourceRepositoryGrant).values(
                installation_id=installation, repository_id=repository,
                access_status='granted', valid_from=start + timedelta(hours=3),
                last_observed_at=start + timedelta(hours=3),
            )
        )
        assert len(connection.execute(
            select(SourceRepositoryGrant.id).where(SourceRepositoryGrant.repository_id == repository)
        ).scalars().all()) == 2
        retained = connection.execute(select(SourceRepository).where(SourceRepository.id == repository)).scalar_one()
        assert retained.provider_presence == 'observed'  # access expiry never deletes the source object


def test_revision_and_branch_reference_are_repository_scoped(source_engine) -> None:
    with source_engine.begin() as connection:
        account = _account(connection, '13')
        first = _repository(connection, account, '11', 'a')
        second = _repository(connection, account, '12', 'b')
        now = datetime.now(UTC)
        sha = 'c' * 40
        first_revision = connection.execute(
            insert(SourceRevision).values(repository_id=first, commit_sha=sha, last_observed_at=now)
        ).inserted_primary_key[0]
        second_revision = connection.execute(
            insert(SourceRevision).values(repository_id=second, commit_sha=sha, last_observed_at=now)
        ).inserted_primary_key[0]
        assert first_revision != second_revision
        branch = connection.execute(
            insert(SourceReference).values(
                repository_id=first, full_ref='refs/heads/main',
                current_revision_id=first_revision, state='active',
            )
        ).inserted_primary_key[0]
        connection.execute(
            insert(SourceReferenceTransition).values(
                reference_id=branch, target_revision_id=first_revision,
                observed_at=now, transition_state='observed',
            )
        )
        assert connection.execute(
            select(SourceReferenceTransition.id).where(
                SourceReferenceTransition.reference_id == branch
            )
        ).scalar_one() is not None


def test_repository_native_id_unique_per_host_not_mutable_representation(source_engine) -> None:
    with source_engine.begin() as connection:
        account = _account(connection, '5')
        _repository(connection, account, '75', 'original')
        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                _repository(connection, account, '75', 'renamed')
        connection.execute(
            insert(SourceRepository).values(
                provider_key='github', host_key='ghes.internal',
                native_repository_id='75', provider_presence='unknown',
            )
        )


def test_identity_schema_contains_no_plaintext_git_auth_material() -> None:
    columns = {column.name for column in SourceInstallation.__table__.columns}
    assert 'integration_instance_id' in columns
    assert 'native_installation_id' in columns
    assert not any(word in column for column in columns for word in ('token', 'secret', 'private_key'))


def test_github_matrix_option_follows_lifecycle() -> None:
    from app.integrations.provider_matrix import provider_kind, provider_options

    provider = provider_kind('source_control', 'github')
    assert provider.lifecycle in {'planned', 'available'}
    assert bool(provider_options('source_control')) == provider.available
