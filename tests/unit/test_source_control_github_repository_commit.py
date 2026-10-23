"""SC-03 committed repository reconciliation and generation fencing contracts.

Ephemeral SQLite unit state only. No GitHub.com API, credential, or production
mutation is performed.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.integrations.source_control.source_control.providers.github import repository_commit
from app.integrations.source_control.source_control.providers.github.repository_commit import (
    RepositoryGenerationError,
    publish_generation,
    record_generation_failure,
    reserve_generation,
)
from app.integrations.source_control.source_control.providers.github.repository_discovery import (
    RepositoryCollection,
    RepositoryObservation,
)
from app.models.integration import IntegrationInstance
from app.models.source_control import (
    GitHubAppCredential,
    SourceAccount,
    SourceInstallation,
    SourceRepository,
    SourceRepositoryCollectionState,
    SourceRepositoryGrant,
)


@pytest.fixture
def state(monkeypatch):
    monkeypatch.setattr(repository_commit, '_admitted', lambda _i: None)
    engine = create_engine('sqlite+pysqlite:///:memory:')
    with engine.connect() as connection:
        connection.exec_driver_sql('PRAGMA foreign_keys = ON')
    IntegrationInstance.metadata.create_all(bind=engine, tables=[
        IntegrationInstance.__table__,
        SourceAccount.__table__,
        GitHubAppCredential.__table__,
        SourceInstallation.__table__,
        SourceRepository.__table__,
        SourceRepositoryGrant.__table__,
        SourceRepositoryCollectionState.__table__,
    ])
    with Session(engine) as session:
        account = SourceAccount(
            provider_key='github', host_key='github.com', native_account_id='2',
            login='old-login', account_type='Organization',
        )
        canonical = IntegrationInstance(
            name='GitHub Test', integration_type='source_control',
            provider_key='github', adapter_key='github_rest_v3',
            enabled=True, lifecycle_status='active', readiness_status='validation_required',
        )
        session.add_all((account, canonical))
        session.flush()
        installation = SourceInstallation(
            integration_instance_id=canonical.id, provider_key='github',
            host_key='github.com', native_app_id='7', native_installation_id='9',
            account_id=account.id, repository_scope='selected', grant_status='unknown',
        )
        session.add(installation)
        session.commit()
        yield session, installation
    engine.dispose()


def _item(native_id='10', *, name='app', archived=False):
    return RepositoryObservation(
        native_id=native_id, owner_native_id='2', owner_login='org',
        name=name, full_name=f'org/{name}', default_branch='main',
        visibility='private', archived=archived,
    )


def _evidence(*items, observed=None, scope='selected'):
    return RepositoryCollection(
        provider_key='github', host_key='github.com',
        app_native_id='7', installation_native_id='9',
        account_native_id='2', account_type='Organization',
        account_login='org', repository_selection=scope,
        expected_count=len(items), repositories=tuple(items),
        observed_at=observed or datetime.now(UTC), pages=1,
    )


def _current(session, installation):
    return session.execute(select(SourceRepositoryGrant).where(
        SourceRepositoryGrant.installation_id == installation.id,
        SourceRepositoryGrant.valid_until.is_(None),
    )).scalars().all()


def test_generation_is_reserved_and_complete_scope_is_committed(state):
    session, installation = state
    lease = reserve_generation(session, installation)
    count = publish_generation(session, installation, lease, _evidence(_item()))
    assert count == 1
    collection = session.get(SourceRepositoryCollectionState, installation.id)
    assert collection.next_generation == 1
    assert collection.pending_generation is None
    assert collection.committed_generation == 1
    assert collection.status == 'committed'
    assert collection.coverage == 'exhaustive_installation_grants'
    assert collection.repository_scope == 'selected'
    assert collection.observed_count == 1
    assert len(_current(session, installation)) == 1
    assert _current(session, installation)[0].access_status == 'granted'
    repo = session.execute(select(SourceRepository)).scalar_one()
    assert repo.native_repository_id == '10'
    assert repo.full_name == 'org/app'
    assert repo.default_branch == 'main'
    assert repo.provider_presence == 'observed'


def test_rename_preserves_native_repository_identity(state):
    session, installation = state
    publish_generation(session, installation, reserve_generation(session, installation), _evidence(_item()))
    before = session.execute(select(SourceRepository)).scalar_one().id
    publish_generation(
        session, installation, reserve_generation(session, installation),
        _evidence(_item(name='new-name', archived=True)),
    )
    repo = session.execute(select(SourceRepository)).scalar_one()
    assert repo.id == before
    assert repo.full_name == 'org/new-name'
    assert repo.archived is True
    assert len(_current(session, installation)) == 1


def test_exhaustive_missing_grant_marks_access_lost_without_deleting_repository(state):
    session, installation = state
    publish_generation(
        session, installation, reserve_generation(session, installation),
        _evidence(_item('10'), _item('11', name='second')),
    )
    publish_generation(
        session, installation, reserve_generation(session, installation),
        _evidence(_item('10')),
    )
    assert len(session.execute(select(SourceRepository)).scalars().all()) == 2
    current = _current(session, installation)
    assert len(current) == 2
    assert {g.access_status for g in current} == {'granted', 'access_lost'}
    history = session.execute(select(SourceRepositoryGrant)).scalars().all()
    assert len(history) == 3
    assert all(r.provider_presence == 'observed' for r in session.execute(
        select(SourceRepository)
    ).scalars().all())


def test_empty_authorized_scope_preserves_evidence_and_revokes_only_grants(state):
    session, installation = state
    publish_generation(session, installation, reserve_generation(session, installation), _evidence(_item()))
    publish_generation(session, installation, reserve_generation(session, installation), _evidence())
    assert len(session.execute(select(SourceRepository)).scalars().all()) == 1
    assert _current(session, installation)[0].access_status == 'access_lost'
    state_row = session.get(SourceRepositoryCollectionState, installation.id)
    assert state_row.observed_count == 0
    assert state_row.coverage == 'exhaustive_installation_grants'


def test_stale_generation_cannot_replace_newer_scan(state):
    session, installation = state
    older = reserve_generation(session, installation)
    current = reserve_generation(session, installation)
    with pytest.raises(RepositoryGenerationError, match='Stale'):
        publish_generation(session, installation, older, _evidence(_item('99')))
    assert session.execute(select(SourceRepository)).scalars().all() == []
    publish_generation(session, installation, current, _evidence(_item()))
    row = session.get(SourceRepositoryCollectionState, installation.id)
    assert row.committed_generation == current.generation


def test_failed_partial_scan_does_not_overwrite_previous_committed_grants(state):
    session, installation = state
    publish_generation(session, installation, reserve_generation(session, installation), _evidence(_item()))
    second = reserve_generation(session, installation)
    assert record_generation_failure(session, installation, second)
    collection = session.get(SourceRepositoryCollectionState, installation.id)
    assert collection.status == 'degraded'
    assert collection.observed_count == 1
    assert collection.committed_generation == 1
    assert _current(session, installation)[0].access_status == 'granted'
    assert 'incomplete' in collection.last_error


def test_wrong_account_scope_rejected_before_writing_repository(state):
    session, installation = state
    generation = reserve_generation(session, installation)
    wrong = _evidence(_item('99'), scope='all')
    with pytest.raises(RepositoryGenerationError, match='mis-scoped'):
        publish_generation(session, installation, generation, wrong)
    assert session.execute(select(SourceRepository)).scalars().all() == []


def test_generation_and_repository_ids_are_installation_scoped(state):
    session, installation = state
    other_account = SourceAccount(
        provider_key='github', host_key='github.com', native_account_id='22',
        account_type='Organization',
    )
    other_canonical = IntegrationInstance(
        name='Other GitHub', integration_type='source_control', provider_key='github',
        adapter_key='github_rest_v3', enabled=True, lifecycle_status='active',
        readiness_status='validation_required',
    )
    session.add_all([other_account, other_canonical])
    session.flush()
    other = SourceInstallation(
        integration_instance_id=other_canonical.id, provider_key='github',
        host_key='github.com', native_app_id='7', native_installation_id='10',
        account_id=other_account.id, repository_scope='selected',
    )
    session.add(other)
    session.commit()
    scoped = reserve_generation(session, installation)
    with pytest.raises(RepositoryGenerationError, match='another installation'):
        publish_generation(session, other, scoped, _evidence(_item('10')))
    assert not session.execute(select(SourceRepository)).scalars().all()


def test_no_provider_authority_no_reservation(state, monkeypatch):
    session, installation = state
    monkeypatch.setattr(
        repository_commit, '_admitted',
        lambda _: (_ for _ in ()).throw(RepositoryGenerationError('not admitted')),
    )
    with pytest.raises(RepositoryGenerationError, match='not admitted'):
        reserve_generation(session, installation)
    assert session.get(SourceRepositoryCollectionState, installation.id) is None



def test_mid_scan_provider_revocation_can_mark_degraded_without_removing_grants(
    state, monkeypatch,
):
    session, installation = state
    publish_generation(
        session, installation, reserve_generation(session, installation),
        _evidence(_item()),
    )
    later = reserve_generation(session, installation)
    monkeypatch.setattr(
        repository_commit, '_admitted',
        lambda _: (_ for _ in ()).throw(RepositoryGenerationError('App revoked')),
    )
    assert record_generation_failure(session, installation, later)
    row = session.get(SourceRepositoryCollectionState, installation.id)
    assert row.status == 'degraded'
    assert row.committed_generation == 1
    assert row.observed_count == 1
    assert _current(session, installation)[0].access_status == 'granted'
