"""SC-03 committed inventory projection never queries GitHub or broadens installation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.integrations.source_control.repository_inventory import read_installation_inventory
from app.models.integration import IntegrationInstance
from app.models.source_control import (
    SourceAccount,
    SourceInstallation,
    SourceReference,
    SourceRepository,
    SourceRepositoryCollectionState,
    SourceRepositoryGrant,
    SourceRevision,
)


@pytest.fixture
def read_db():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    IntegrationInstance.metadata.create_all(
        bind=engine,
        tables=[
            IntegrationInstance.__table__,
            SourceAccount.__table__,
            SourceInstallation.__table__,
            SourceRepository.__table__,
            SourceRepositoryGrant.__table__,
            SourceRepositoryCollectionState.__table__,
            SourceRevision.__table__,
            SourceReference.__table__,
        ],
    )
    with Session(engine) as session:
        account = SourceAccount(
            provider_key='github',
            host_key='github.com',
            native_account_id='1',
        )
        session.add(account)
        session.flush()
        installations = []
        for number in (5, 6):
            provider = IntegrationInstance(
                name=f'Github {number}',
                integration_type='source_control',
                provider_key='github',
                adapter_key='github_rest_v3',
                lifecycle_status='active',
                readiness_status='validation_required',
            )
            session.add(provider)
            session.flush()
            installation = SourceInstallation(
                integration_instance_id=provider.id,
                account_id=account.id,
                host_key='github.com',
                provider_key='github',
                native_app_id='2',
                native_installation_id=str(number),
                repository_scope='selected',
            )
            session.add(installation)
            session.flush()
            installations.append(installation.id)
        repo = SourceRepository(
            provider_key='github',
            host_key='github.com',
            native_repository_id='15',
            full_name='org/private-repo',
            default_branch='main',
            visibility='private',
            provider_presence='observed',
        )
        session.add(repo)
        session.flush()
        now = datetime.now(UTC)
        session.add(
            SourceRepositoryGrant(
                installation_id=installations[0],
                repository_id=repo.id,
                access_status='granted',
                valid_from=now,
                last_observed_at=now,
            )
        )
        session.add(
            SourceRepositoryCollectionState(
                installation_id=installations[0],
                next_generation=1,
                committed_generation=1,
                status='committed',
                repository_scope='selected',
                coverage='exhaustive_installation_grants',
                observed_count=1,
                last_committed_at=now,
            )
        )
        session.commit()
        yield session, installations
    engine.dispose()


def test_projection_uses_only_authorized_installation(read_db):
    session, installations = read_db
    one = read_installation_inventory(session, authorized_installation_id=installations[0])
    assert one.total == 1
    assert len(one.rows) == 1
    assert one.rows[0].full_name == 'org/private-repo'
    other = read_installation_inventory(session, authorized_installation_id=installations[1])
    assert other.total is None
    assert other.rows == ()
    assert other.observed_count is None


def test_missing_coverage_never_infers_empty_source_scope(read_db):
    session, installations = read_db
    other = read_installation_inventory(session, authorized_installation_id=installations[1])
    assert other.collection_status == 'not_collected'
    assert other.coverage == 'unknown'
    assert other.total is None


@pytest.mark.parametrize('size', [0, 1, 3, 100, True])
def test_pagination_only_uses_kaori_page_sizes(read_db, size):
    session, installations = read_db
    with pytest.raises(ValueError):
        read_installation_inventory(
            session,
            authorized_installation_id=installations[0],
            per_page=size,
        )


@pytest.mark.parametrize('identity', [0, -1, True, None])
def test_unqualified_installation_is_rejected(read_db, identity):
    session, _ = read_db
    with pytest.raises(ValueError):
        read_installation_inventory(session, authorized_installation_id=identity)


def test_no_live_provider_request_in_read_projection():
    from pathlib import Path
    source = (
        Path(__file__).resolve().parents[2] / 'app/integrations/source_control/repository_inventory.py'
    ).read_text()
    assert 'requests' not in source
    assert 'GitHubAppClient' not in source
    assert 'access_tokens' not in source
    assert 'integration_instance_id' not in source.split('def read_installation_inventory(')[1]



def test_exact_sha_is_a_committed_optional_projection_not_a_live_lookup(read_db):
    session, installations = read_db
    before = read_installation_inventory(session, authorized_installation_id=installations[0])
    assert before.rows[0].exact_default_branch_sha is None
    assert before.rows[0].revision_observed_at is None

    repository = session.execute(select(SourceRepository)).scalar_one()
    now = datetime.now(UTC)
    revision = SourceRevision(
        repository_id=repository.id,
        commit_sha='a' * 40,
        last_observed_at=now,
    )
    session.add(revision)
    session.flush()
    session.add(
        SourceReference(
            repository_id=repository.id,
            full_ref='refs/heads/main',
            current_revision_id=revision.id,
            state='observed',
            last_observed_at=now,
        )
    )
    session.commit()

    after = read_installation_inventory(session, authorized_installation_id=installations[0])
    assert after.rows[0].exact_default_branch_sha == 'a' * 40
    assert after.rows[0].revision_observed_at is not None

    # The other installation has never received a successful inventory generation.
    other = read_installation_inventory(session, authorized_installation_id=installations[1])
    assert other.rows == () and other.total is None


def test_branch_change_does_not_fabricate_latest_sha_for_unobserved_ref(read_db):
    session, installations = read_db
    repository = session.execute(select(SourceRepository)).scalar_one()
    revision = SourceRevision(
        repository_id=repository.id,
        commit_sha='b' * 40,
        last_observed_at=datetime.now(UTC),
    )
    session.add(revision)
    session.flush()
    session.add(
        SourceReference(
            repository_id=repository.id,
            full_ref='refs/heads/old-main',
            current_revision_id=revision.id,
            state='observed',
            last_observed_at=datetime.now(UTC),
        )
    )
    session.commit()
    page = read_installation_inventory(session, authorized_installation_id=installations[0])
    assert page.rows[0].default_branch == 'main'
    assert page.rows[0].exact_default_branch_sha is None


def test_committed_repository_filters_use_matching_counts_and_authorized_scope(read_db):
    session, installations = read_db
    installation_id = installations[0]

    baseline = read_installation_inventory(session, authorized_installation_id=installation_id)
    assert baseline.total == 1
    assert baseline.matching_total == 1

    by_name = read_installation_inventory(session, authorized_installation_id=installation_id, search='PRIVATE-REPO')
    assert by_name.total == 1
    assert by_name.matching_total == 1
    assert by_name.rows[0].full_name == 'org/private-repo'

    by_native_id = read_installation_inventory(session, authorized_installation_id=installation_id, search='15')
    assert by_native_id.matching_total == 1

    no_match = read_installation_inventory(session, authorized_installation_id=installation_id, visibility='public')
    assert no_match.total == 1
    assert no_match.matching_total == 0
    assert no_match.rows == ()
    assert no_match.page == 1

    archived = read_installation_inventory(session, authorized_installation_id=installation_id, archived='archived')
    assert archived.matching_total == 0
    unknown_state = read_installation_inventory(session, authorized_installation_id=installation_id, archived='unknown')
    assert unknown_state.matching_total == 1

    other = read_installation_inventory(
        session,
        authorized_installation_id=installations[1],
        search='private',
        visibility='private',
    )
    assert other.total is None
    assert other.matching_total is None
    assert other.rows == ()


def test_committed_repository_search_is_literal_and_pages_clamp(read_db):
    session, installations = read_db
    installation_id = installations[0]

    for literal in ('%', '_', 'not-present'):
        result = read_installation_inventory(session, authorized_installation_id=installation_id, search=literal)
        assert result.total == 1
        assert result.matching_total == 0
        assert result.rows == ()

    last = read_installation_inventory(session, authorized_installation_id=installation_id, page=99, per_page=5)
    assert last.page == 1
    assert last.total == last.matching_total == 1
    assert len(last.rows) == 1
