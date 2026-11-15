"""Read-only, authorized, committed Source Control portfolio coverage contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

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
from app.source_control.repository_coverage import read_repository_coverage


@pytest.fixture
def coverage_db():
    engine = create_engine('sqlite+pysqlite:///:memory:')
    IntegrationInstance.metadata.create_all(
        bind=engine,
        tables=[
            IntegrationInstance.__table__,
            SourceAccount.__table__,
            SourceInstallation.__table__,
            SourceRepository.__table__,
            SourceRepositoryGrant.__table__,
            SourceReference.__table__,
            SourceRevision.__table__,
            SourceRepositoryCollectionState.__table__,
        ],
    )
    with Session(engine) as session:
        now = datetime.now(UTC)
        account = SourceAccount(
            provider_key='github',
            host_key='github.com',
            native_account_id='42',
            account_type='Organization',
            login='org',
        )
        session.add(account)
        session.flush()
        installations = []
        for number in ('100', '200'):
            connection = IntegrationInstance(
                name='GitHub ' + number,
                integration_type='source_control',
                provider_key='github',
                adapter_key='github_rest_v3',
                lifecycle_status='active',
                readiness_status='validation_required',
            )
            session.add(connection)
            session.flush()
            installation = SourceInstallation(
                integration_instance_id=connection.id,
                provider_key='github',
                host_key='github.com',
                native_app_id='5',
                native_installation_id=number,
                account_id=account.id,
                repository_scope='selected',
            )
            session.add(installation)
            session.flush()
            installations.append(installation.id)
        repo = SourceRepository(
            provider_key='github',
            host_key='github.com',
            native_repository_id='7',
            full_name='org/repo-one',
            visibility='private',
            archived=False,
            default_branch='main',
            provider_presence='observed',
        )
        session.add(repo)
        session.flush()
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
        yield session, installations, repo
    engine.dispose()


def _count(snapshot, family, label):
    return next(category.count for category in getattr(snapshot, family) if category.label == label)


def test_single_repository_shows_source_facts_and_missing_exact_sha(coverage_db):
    session, installations, _ = coverage_db
    result = read_repository_coverage(session, authorized_installation_id=installations[0])
    assert result.collected
    assert result.grant_count == result.observed_count == 1
    assert result.grant_count_matches_observation is True
    assert result.single_repository == 'org/repo-one'
    assert _count(result, 'visibility', 'Private') == 1
    assert _count(result, 'lifecycle', 'Active') == 1
    assert _count(result, 'references', 'Branch Only') == 1
    assert result.attention_count == 1
    assert result.attention[0].reasons == ('Exact SHA Missing',)
    assert result.attention[0].name == 'org/repo-one'


def test_uncollected_installation_never_appears_as_verified_zero(coverage_db):
    session, installations, _ = coverage_db
    missing = read_repository_coverage(session, authorized_installation_id=installations[1])
    assert not missing.collected
    assert missing.grant_count is None
    assert missing.observed_count is None
    assert missing.attention_count is None
    assert not missing.visibility
    assert not missing.attention


def test_qualified_zero_distinguished_from_unknown_and_multi_repo(coverage_db):
    session, installations, _ = coverage_db
    session.add(
        SourceRepositoryCollectionState(
            installation_id=installations[1],
            next_generation=1,
            committed_generation=1,
            status='committed',
            repository_scope='selected',
            coverage='exhaustive_installation_grants',
            observed_count=0,
            last_committed_at=datetime.now(UTC),
        )
    )
    session.commit()
    empty = read_repository_coverage(session, authorized_installation_id=installations[1])
    assert empty.collected
    assert empty.grant_count == empty.observed_count == 0
    assert empty.attention_count == 0
    assert empty.single_repository is None
    assert all(category.count == 0 for category in empty.visibility)


def test_multiple_repository_metadata_and_exact_sha_are_distribution_not_forecast(coverage_db):
    session, installations, first = coverage_db
    now = datetime.now(UTC)
    revision = SourceRevision(repository_id=first.id, commit_sha='a' * 40, last_observed_at=now)
    session.add(revision)
    session.flush()
    session.add(
        SourceReference(
            repository_id=first.id,
            full_ref='refs/heads/main',
            current_revision_id=revision.id,
            state='observed',
            last_observed_at=now,
        )
    )
    other = SourceRepository(
        provider_key='github',
        host_key='github.com',
        native_repository_id='8',
        full_name='org/repo-two',
        visibility='public',
        archived=True,
        default_branch=None,
        provider_presence='observed',
    )
    session.add(other)
    session.flush()
    session.add(
        SourceRepositoryGrant(
            installation_id=installations[0],
            repository_id=other.id,
            access_status='granted',
            valid_from=now,
            last_observed_at=now,
        )
    )
    state = session.get(SourceRepositoryCollectionState, installations[0])
    assert state is not None
    state.observed_count = 2
    session.commit()
    result = read_repository_coverage(session, authorized_installation_id=installations[0])
    assert result.grant_count == result.observed_count == 2
    assert result.single_repository is None
    assert _count(result, 'visibility', 'Private') == 1
    assert _count(result, 'visibility', 'Public') == 1
    assert _count(result, 'lifecycle', 'Archived') == 1
    assert _count(result, 'references', 'Exact SHA') == 1
    assert _count(result, 'references', 'Missing Branch') == 1
    assert next(category.percent for category in result.visibility if category.label == 'Private') == 50
    assert result.attention_count == 1
    assert result.attention[0].name == 'org/repo-two'
    assert 'Default Branch Missing' in result.attention[0].reasons


def test_overlapping_grant_not_summed_or_exposed_through_another_installation(coverage_db):
    session, installations, repo = coverage_db
    now = datetime.now(UTC)
    session.add(
        SourceRepositoryGrant(
            installation_id=installations[1],
            repository_id=repo.id,
            access_status='granted',
            valid_from=now,
            last_observed_at=now,
        )
    )
    session.add(
        SourceRepositoryCollectionState(
            installation_id=installations[1],
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
    one = read_repository_coverage(session, authorized_installation_id=installations[0])
    two = read_repository_coverage(session, authorized_installation_id=installations[1])
    assert one.grant_count == 1
    assert two.grant_count == 1
    assert one.single_repository == two.single_repository == 'org/repo-one'


def test_attention_samples_are_bounded_to_five_and_collector_mismatch_visible(coverage_db):
    session, installations, _ = coverage_db
    now = datetime.now(UTC)
    for number in range(10, 16):
        repo = SourceRepository(
            provider_key='github',
            host_key='github.com',
            native_repository_id=str(number),
            full_name=f'org/missing-{number}',
            visibility=None,
            archived=None,
            default_branch=None,
        )
        session.add(repo)
        session.flush()
        session.add(
            SourceRepositoryGrant(
                installation_id=installations[0],
                repository_id=repo.id,
                access_status='granted',
                valid_from=now,
                last_observed_at=now,
            )
        )
    session.commit()
    result = read_repository_coverage(session, authorized_installation_id=installations[0])
    assert result.grant_count == 7
    assert result.observed_count == 1
    assert result.grant_count_matches_observation is False
    assert result.attention_count == 7
    assert len(result.attention) == 5
    assert result.attention[0].name.startswith('org/missing-')
    assert _count(result, 'visibility', 'Unknown') == 6
    assert _count(result, 'lifecycle', 'Unknown') == 6


@pytest.mark.parametrize('installation_id', [None, 0, -1, True, '1'])
def test_projection_requires_previously_authorized_positive_installation_id(coverage_db, installation_id):
    session, _, _ = coverage_db
    with pytest.raises(ValueError):
        read_repository_coverage(session, authorized_installation_id=installation_id)


def test_coverage_projection_is_read_only_and_never_calls_provider():
    text = (
        Path(__file__).resolve().parents[2] / 'app/source_control/repository_coverage.py'
    ).read_text()
    assert 'GitHubAppClient' not in text
    assert 'requests.get' not in text
    assert 'session.commit(' not in text
    assert 'SourceRepositoryGrant.installation_id == authorized_installation_id' in text
    assert 'SourceRepositoryGrant.valid_until.is_(None)' in text
    assert '.limit(_MAX_ATTENTION_ROWS)' in text
