"""SC-03 exact revision identity and mutable default-branch transition persistence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.integrations.source_control.source_control.providers.github import reference_commit
from app.integrations.source_control.source_control.providers.github.default_branch import (
    DefaultBranchEvidence,
)
from app.integrations.source_control.source_control.providers.github.repository_commit import (
    RepositoryGenerationError,
)
from app.models.integration import IntegrationInstance
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
def refs(monkeypatch):
    monkeypatch.setattr(reference_commit, '_admitted', lambda _: None)
    engine = create_engine('sqlite+pysqlite:///:memory:')
    IntegrationInstance.metadata.create_all(bind=engine, tables=[
        IntegrationInstance.__table__,
        SourceAccount.__table__,
        SourceInstallation.__table__,
        SourceRepository.__table__,
        SourceRepositoryGrant.__table__,
        SourceRevision.__table__,
        SourceReference.__table__,
        SourceReferenceTransition.__table__,
    ])
    with Session(engine) as session:
        account = SourceAccount(
            provider_key='github', host_key='github.com', native_account_id='22',
            account_type='Organization', login='org',
        )
        connection = IntegrationInstance(
            integration_type='source_control', provider_key='github',
            adapter_key='github_rest_v3', name='Source App',
            enabled=True, lifecycle_status='active',
            readiness_status='validation_required',
        )
        session.add_all([account, connection])
        session.flush()
        installation = SourceInstallation(
            integration_instance_id=connection.id,
            provider_key='github', host_key='github.com',
            native_app_id='5', native_installation_id='8',
            account_id=account.id, repository_scope='selected',
        )
        repo = SourceRepository(
            provider_key='github', host_key='github.com',
            native_repository_id='101', account_id=account.id,
            name='service', full_name='org/service', default_branch='main',
            provider_presence='observed',
        )
        session.add_all([installation, repo])
        session.flush()
        grant = SourceRepositoryGrant(
            installation_id=installation.id, repository_id=repo.id,
            access_status='granted', valid_from=datetime.now(UTC),
            last_observed_at=datetime.now(UTC),
        )
        session.add(grant)
        session.commit()
        yield session, installation, repo
    engine.dispose()


def _evidence(installation, repo, sha='a' * 40, observed=None):
    return DefaultBranchEvidence(
        repository_id=repo.id, installation_id=installation.id,
        native_repository_id=repo.native_repository_id,
        full_ref='refs/heads/main', commit_sha=sha,
        observed_at=observed or datetime.now(UTC),
    )


def test_first_exact_sha_stores_native_scoped_revision_and_reference(refs):
    session, installation, repo = refs
    assert reference_commit.publish_default_branch_revision(
        session, installation=installation, evidence=_evidence(installation, repo)
    )
    revisions = session.execute(select(SourceRevision)).scalars().all()
    refs = session.execute(select(SourceReference)).scalars().all()
    changes = session.execute(select(SourceReferenceTransition)).scalars().all()
    assert len(revisions) == len(refs) == len(changes) == 1
    assert revisions[0].commit_sha == 'a' * 40
    assert revisions[0].repository_id == repo.id
    assert refs[0].current_revision_id == revisions[0].id
    assert refs[0].full_ref == 'refs/heads/main'
    assert changes[0].transition_state == 'observed'


def test_force_push_or_fast_forward_retains_both_exact_sha_identifiers(refs):
    session, installation, repo = refs
    start = datetime.now(UTC)
    reference_commit.publish_default_branch_revision(
        session, installation=installation,
        evidence=_evidence(installation, repo, observed=start),
    )
    assert reference_commit.publish_default_branch_revision(
        session, installation=installation,
        evidence=_evidence(installation, repo, 'b' * 40, start + timedelta(seconds=1)),
    )
    assert len(session.execute(select(SourceRevision)).scalars().all()) == 2
    refs = session.execute(select(SourceReference)).scalar_one()
    assert refs.current_revision.commit_sha == 'b' * 40
    changes = session.execute(
        select(SourceReferenceTransition).order_by(SourceReferenceTransition.observed_at)
    ).scalars().all()
    assert [entry.transition_state for entry in changes] == ['observed', 'moved']
    assert [entry.target_revision.commit_sha for entry in changes] == ['a' * 40, 'b' * 40]


def test_reobserving_identical_tip_does_not_fabricate_transition(refs):
    session, installation, repo = refs
    start = datetime.now(UTC)
    reference_commit.publish_default_branch_revision(
        session, installation=installation, evidence=_evidence(installation, repo, observed=start),
    )
    changed = reference_commit.publish_default_branch_revision(
        session, installation=installation,
        evidence=_evidence(installation, repo, observed=start + timedelta(seconds=1)),
    )
    assert changed is False
    assert len(session.execute(select(SourceReferenceTransition)).scalars().all()) == 1


def test_out_of_order_observation_cannot_overwrite_new_tip(refs):
    session, installation, repo = refs
    now = datetime.now(UTC)
    reference_commit.publish_default_branch_revision(
        session, installation=installation, evidence=_evidence(installation, repo, observed=now),
    )
    with pytest.raises(RepositoryGenerationError, match='Stale'):
        reference_commit.publish_default_branch_revision(
            session, installation=installation,
            evidence=_evidence(installation, repo, 'b' * 40, now - timedelta(seconds=1)),
        )
    assert session.execute(select(SourceReference)).scalar_one().current_revision.commit_sha == 'a' * 40
    assert len(session.execute(select(SourceRevision)).scalars().all()) == 1


def test_changed_default_branch_and_revoked_grant_denied(refs):
    session, installation, repo = refs
    evidence = _evidence(installation, repo)
    repo.default_branch = 'release'
    session.flush()
    with pytest.raises(RepositoryGenerationError, match='changed before publication'):
        reference_commit.publish_default_branch_revision(
            session, installation=installation, evidence=evidence,
        )
    repo.default_branch = 'main'
    grant = session.execute(select(SourceRepositoryGrant)).scalar_one()
    grant.access_status = 'access_lost'
    session.flush()
    with pytest.raises(RepositoryGenerationError, match='no longer authorizes'):
        reference_commit.publish_default_branch_revision(
            session, installation=installation, evidence=evidence,
        )


def test_cross_installation_delivery_cannot_publish_revision(refs):
    session, installation, repo = refs
    evidence = _evidence(installation, repo)
    altered = DefaultBranchEvidence(
        repository_id=evidence.repository_id,
        native_repository_id=evidence.native_repository_id,
        installation_id=installation.id + 99,
        full_ref=evidence.full_ref, commit_sha=evidence.commit_sha,
        observed_at=evidence.observed_at,
    )
    with pytest.raises(RepositoryGenerationError, match='mis-scoped'):
        reference_commit.publish_default_branch_revision(
            session, installation=installation, evidence=altered,
        )


def test_no_full_sha_no_persistence(refs):
    session, installation, repo = refs
    with pytest.raises(RepositoryGenerationError, match='invalid'):
        reference_commit.publish_default_branch_revision(
            session, installation=installation,
            evidence=_evidence(installation, repo, 'abc'),
        )
    assert session.execute(select(SourceReference)).scalars().all() == []
    assert session.execute(select(SourceRevision)).scalars().all() == []
