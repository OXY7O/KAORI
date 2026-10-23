"""Generation-fenced committed GitHub repository inventory for SC-03 #2742.

Provider collection is separate from publication. Only complete evidence from
the exact reserved generation can update native identities, scoped grants and
collection freshness. Access lost is never GitHub repository deletion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.provider_matrix import provider_kind
from app.integrations.source_control.source_control.providers.github.repository_discovery import (
    RepositoryCollection,
)
from app.integrations.source_control.source_control.providers.github.transport import GitHubProviderError
from app.models.source_control import (
    SourceInstallation,
    SourceRepository,
    SourceRepositoryCollectionState,
    SourceRepositoryGrant,
)


class RepositoryGenerationError(RuntimeError):
    """A scan is stale, incomplete, or outside its authorized installation."""


@dataclass(frozen=True, slots=True)
class RepositoryGeneration:
    installation_id: int
    generation: int


def _admitted(installation: SourceInstallation) -> None:
    if not provider_kind('source_control', 'github').available:
        raise RepositoryGenerationError('Source Control repository publishing is not admitted.')
    canonical = installation.integration_instance
    account = installation.account
    app = installation.github_app_credential
    if (
        installation.id is None
        or canonical is None
        or not canonical.enabled
        or canonical.lifecycle_status != 'active'
        or canonical.integration_type != 'source_control'
        or canonical.provider_key != 'github'
        or canonical.adapter_key != 'github_rest_v3'
        or installation.integration_instance_id != canonical.id
        or installation.provider_key != 'github'
        or installation.host_key != 'github.com'
        or account is None
        or account.provider_key != installation.provider_key
        or account.host_key != installation.host_key
        or installation.account_id != account.id
        or app is None
        or not app.enabled
        or app.host_key != installation.host_key
        or app.native_app_id != installation.native_app_id
        or installation.github_app_credential_id != app.id
    ):
        raise RepositoryGenerationError('Source Control installation is not eligible for collection.')


def reserve_generation(session: Session, installation: SourceInstallation) -> RepositoryGeneration:
    """Persist a fencing number before starting network work.

    A competing first registration may hit the PK constraint; the caller must
    retry after rollback rather than perform provider work without a lease.
    This commits the reservation so no DB lock is held during pagination.
    """
    _admitted(installation)
    state = session.get(
        SourceRepositoryCollectionState, installation.id, with_for_update=True
    )
    if state is None:
        state = SourceRepositoryCollectionState(
            installation_id=installation.id,
            next_generation=0,
            committed_generation=0,
            status='not_collected',
            repository_scope='unknown',
            coverage='unknown',
        )
        session.add(state)
        session.flush()
    state.next_generation += 1
    number = state.next_generation
    state.pending_generation = number
    state.status = 'collecting'
    state.last_started_at = datetime.now(UTC)
    session.commit()
    return RepositoryGeneration(installation_id=installation.id, generation=number)


def _same_authority(installation: SourceInstallation, evidence: RepositoryCollection) -> None:
    account = installation.account
    if (
        account is None
        or evidence.provider_key != installation.provider_key
        or evidence.host_key != installation.host_key
        or evidence.app_native_id != installation.native_app_id
        or evidence.installation_native_id != installation.native_installation_id
        or evidence.account_native_id != account.native_account_id
        or evidence.repository_selection not in {'all', 'selected'}
        or evidence.repository_selection != installation.repository_scope
        or evidence.expected_count != len(evidence.repositories)
        or evidence.observed_at.tzinfo is None
        or len({item.native_id for item in evidence.repositories}) != len(evidence.repositories)
        or any(item.owner_native_id != account.native_account_id for item in evidence.repositories)
    ):
        raise RepositoryGenerationError('GitHub collection evidence is incomplete or mis-scoped.')


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _later(now: datetime, earlier: datetime) -> datetime:
    return max(now, _utc(earlier) + timedelta(microseconds=1))


def publish_generation(
    session: Session,
    installation: SourceInstallation,
    lease: RepositoryGeneration,
    evidence: RepositoryCollection,
) -> int:
    """Atomically commit complete authorized evidence or publish nothing.

    The caller must never synthesize RepositoryCollection from a webhook.
    Only the signed-installation client collection may produce this evidence.
    """
    _admitted(installation)
    if lease.installation_id != installation.id or lease.generation <= 0:
        raise RepositoryGenerationError('Source Control generation belongs to another installation.')
    _same_authority(installation, evidence)
    state = session.get(
        SourceRepositoryCollectionState, installation.id, with_for_update=True
    )
    if (
        state is None
        or state.pending_generation != lease.generation
        or state.next_generation != lease.generation
        or state.committed_generation >= lease.generation
    ):
        raise RepositoryGenerationError('Stale Source Control repository generation; no changes committed.')

    account = installation.account
    assert account is not None
    if account.last_observed_at is None or _utc(account.last_observed_at) <= evidence.observed_at:
        account.login = evidence.account_login
        account.account_type = evidence.account_type
        account.last_observed_at = evidence.observed_at

    grants = session.execute(
        select(SourceRepositoryGrant)
        .where(
            SourceRepositoryGrant.installation_id == installation.id,
            SourceRepositoryGrant.valid_until.is_(None),
        ).with_for_update()
    ).scalars().all()
    active = {grant.repository_id: grant for grant in grants}
    repository_ids: set[int] = set()
    new_grants: list[tuple[int, str, datetime]] = []
    observation_time = evidence.observed_at

    for item in evidence.repositories:
        repo = session.execute(
            select(SourceRepository).where(
                SourceRepository.provider_key == installation.provider_key,
                SourceRepository.host_key == installation.host_key,
                SourceRepository.native_repository_id == item.native_id,
            ).with_for_update()
        ).scalar_one_or_none()
        if repo is None:
            repo = SourceRepository(
                provider_key=installation.provider_key,
                host_key=installation.host_key,
                native_repository_id=item.native_id,
            )
            session.add(repo)
            session.flush()
        # A second installation can observe the same native repository. An
        # older scan must not revert owner, rename, branch or archive metadata.
        if repo.last_observed_at is None or _utc(repo.last_observed_at) <= observation_time:
            repo.account_id = account.id
            repo.name = item.name
            repo.full_name = item.full_name
            # Optional evidence absent from a provider page is UNKNOWN,
            # not proof an already-observed value should be erased.
            if item.default_branch is not None:
                repo.default_branch = item.default_branch
            if item.visibility is not None:
                repo.visibility = item.visibility
            if item.archived is not None:
                repo.archived = item.archived
            repo.provider_presence = 'observed'
            repo.last_observed_at = observation_time
        repository_ids.add(repo.id)
        grant = active.get(repo.id)
        if grant is not None and grant.access_status == 'granted':
            grant.last_observed_at = observation_time
        else:
            changed_at = observation_time
            if grant is not None:
                changed_at = _later(changed_at, grant.valid_from)
                grant.valid_until = changed_at
            new_grants.append((repo.id, 'granted', changed_at))

    # Exhaustive absence is *installation grant access lost* only. All native
    # repositories remain in committed history with independent presence.
    for repo_id, grant in active.items():
        if repo_id not in repository_ids and grant.access_status == 'granted':
            changed_at = _later(observation_time, grant.valid_from)
            grant.valid_until = changed_at
            new_grants.append((repo_id, 'access_lost', changed_at))
    # Close former currently active grants before opening replacement rows,
    # respecting the partial unique DB index even if SQLAlchemy reorders DML.
    session.flush()
    for repository_id, status, start in new_grants:
        session.add(SourceRepositoryGrant(
            installation_id=installation.id,
            repository_id=repository_id,
            access_status=status,
            valid_from=start,
            last_observed_at=observation_time,
        ))

    state.committed_generation = lease.generation
    state.pending_generation = None
    state.repository_scope = evidence.repository_selection
    state.status = 'committed'
    state.coverage = 'exhaustive_installation_grants'
    state.observed_count = evidence.expected_count
    state.last_observed_at = observation_time
    state.last_committed_at = datetime.now(UTC)
    state.last_error = None
    installation.last_observed_at = observation_time
    session.commit()
    return evidence.expected_count


def record_generation_failure(
    session: Session,
    installation: SourceInstallation,
    lease: RepositoryGeneration,
) -> bool:
    """Do not touch prior grants/counts when pagination or auth failed."""
    _admitted(installation)
    state = session.get(
        SourceRepositoryCollectionState, installation.id, with_for_update=True
    )
    if state is None or lease.installation_id != installation.id or state.pending_generation != lease.generation:
        return False
    state.pending_generation = None
    state.status = 'degraded'
    state.last_error = 'GitHub repository discovery incomplete; last committed scope retained.'
    session.commit()
    return True
