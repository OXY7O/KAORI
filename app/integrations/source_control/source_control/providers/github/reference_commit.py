"""Commit exactly qualified GitHub source revision and mutable ref transitions.

SC-03 #2742. Collection is provider authoritative, but publication needs a
still-active installation grant and consistent native repository identity.
No source file content, webhook payload, token, or Git clone is persisted.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.source_control.source_control.providers.github.default_branch import (
    DefaultBranchEvidence,
)
from app.integrations.source_control.source_control.providers.github.repository_commit import (
    RepositoryGenerationError,
    _admitted,
)
from app.models.source_control import (
    SourceInstallation,
    SourceReference,
    SourceReferenceTransition,
    SourceRepository,
    SourceRepositoryGrant,
    SourceRevision,
)

_SHA1 = re.compile(r'[0-9a-f]{40}')


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def publish_default_branch_revision(
    session: Session,
    *,
    installation: SourceInstallation,
    evidence: DefaultBranchEvidence,
) -> bool:
    """Persist a reference movement only when source identity and grant agree.

    Returns False on an already-observed identical pointer. Fencing is per
    SourceReference observation time, unlike the separate per-installation
    exhaustive inventory generation; branch pointers need not be consistent
    with a page-count inventory snapshot.
    """
    _admitted(installation)
    if (
        installation.id is None or installation.account is None
        or evidence.installation_id != installation.id
        or evidence.observed_at.tzinfo is None
        or _SHA1.fullmatch(evidence.commit_sha) is None
        or not evidence.full_ref.startswith('refs/heads/')
    ):
        raise RepositoryGenerationError('Exact branch evidence is invalid or mis-scoped.')
    repo = session.get(SourceRepository, evidence.repository_id, with_for_update=True)
    if (
        repo is None or repo.provider_key != 'github'
        or repo.host_key != installation.host_key
        or repo.native_repository_id != evidence.native_repository_id
        or repo.account_id != installation.account.id
        or not repo.default_branch
        or evidence.full_ref != f'refs/heads/{repo.default_branch}'
    ):
        raise RepositoryGenerationError('Repository identity or default branch changed before publication.')

    grant = session.execute(
        select(SourceRepositoryGrant.id)
        .where(
            SourceRepositoryGrant.installation_id == installation.id,
            SourceRepositoryGrant.repository_id == repo.id,
            SourceRepositoryGrant.access_status == 'granted',
            SourceRepositoryGrant.valid_until.is_(None),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if grant is None:
        raise RepositoryGenerationError('Current installation grant no longer authorizes this revision.')

    ref = session.execute(
        select(SourceReference).where(
            SourceReference.repository_id == repo.id,
            SourceReference.full_ref == evidence.full_ref,
        ).with_for_update()
    ).scalar_one_or_none()
    if ref is not None and ref.last_observed_at is not None:
        if _utc(ref.last_observed_at) > evidence.observed_at:
            raise RepositoryGenerationError('Stale branch observation cannot replace newer committed evidence.')
        if _utc(ref.last_observed_at) == evidence.observed_at:
            raise RepositoryGenerationError('Duplicate observation timestamp is not an ordered update.')

    revision = session.execute(
        select(SourceRevision).where(
            SourceRevision.repository_id == repo.id,
            SourceRevision.commit_sha == evidence.commit_sha,
        )
    ).scalar_one_or_none()
    if revision is None:
        revision = SourceRevision(
            repository_id=repo.id, commit_sha=evidence.commit_sha,
            last_observed_at=evidence.observed_at,
        )
        session.add(revision)
        session.flush()
    elif _utc(revision.last_observed_at) < evidence.observed_at:
        revision.last_observed_at = evidence.observed_at

    created = ref is None
    moved = created or ref.current_revision_id != revision.id
    if ref is None:
        ref = SourceReference(
            repository_id=repo.id, full_ref=evidence.full_ref,
            state='observed', current_revision_id=revision.id,
            last_observed_at=evidence.observed_at,
        )
        session.add(ref)
        session.flush()
    else:
        ref.current_revision_id = revision.id
        ref.state = 'observed'
        ref.last_observed_at = evidence.observed_at

    if moved:
        session.add(SourceReferenceTransition(
            reference_id=ref.id,
            target_revision_id=revision.id,
            transition_state='observed' if created else 'moved',
            observed_at=evidence.observed_at,
        ))
    session.commit()
    return moved
