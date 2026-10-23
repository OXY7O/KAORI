"""Bounded orchestration of one authorized source-repository collection attempt.

This is an inert worker-callable service, NOT a second scheduler or Celery
task. The SC-03 authoritative worker and canonical JobExecution dispatcher
must be separately admitted before calling this in production.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.source_control.source_control.providers.github.default_branch import (
    collect_default_branch_revision,
)
from app.integrations.source_control.source_control.providers.github.reference_commit import (
    publish_default_branch_revision,
)
from app.integrations.source_control.source_control.providers.github.repository_commit import (
    RepositoryGenerationError,
    publish_generation,
    record_generation_failure,
    reserve_generation,
)
from app.integrations.source_control.source_control.providers.github.repository_discovery import (
    collect_installation_repositories,
)
from app.integrations.source_control.source_control.providers.github.transport import GitHubProviderError
from app.models.source_control import (
    SourceInstallation, SourceRepository, SourceRepositoryGrant,
)


@dataclass(frozen=True, slots=True)
class CollectionOutcome:
    installation_id: int
    generation: int
    status: str
    observed_count: int | None
    committed_revisions: int = 0
    revision_failures: int = 0
    unchecked_revisions: int = 0


def synchronize_installation(
    session: Session, installation: SourceInstallation
) -> CollectionOutcome:
    """Reserve -> authorized exhaustive collection -> fenced committed publish.

    Safe failure preserves prior committed records/counts. No retry loop,
    task dispatch, new queue, webhook-derived repository mutation or
    unauthorized provider fallback is introduced here.
    """
    generation = reserve_generation(session, installation)
    try:
        evidence = collect_installation_repositories(installation)
    except Exception:
        session.rollback()
        record_generation_failure(session, installation, generation)
        raise
    try:
        count = publish_generation(session, installation, generation, evidence)
    except Exception:
        session.rollback()
        # A newer reservation or collection always wins. Only the still-owned
        # pending generation can be marked degraded; committed rows stay intact.
        record_generation_failure(session, installation, generation)
        raise
    # Each branch observation is independently authoritative and best-effort.
    # Exact SHA collection never backdates or revokes an exhaustive repository
    # grant scan. Bound calls to avoid external API storms on large tenants.
    target_ids = list(session.scalars(
        select(SourceRepository.id)
        .join(SourceRepositoryGrant, SourceRepositoryGrant.repository_id == SourceRepository.id)
        .where(
            SourceRepositoryGrant.installation_id == installation.id,
            SourceRepositoryGrant.access_status == 'granted',
            SourceRepositoryGrant.valid_until.is_(None),
            SourceRepository.default_branch.is_not(None),
        )
        .order_by(SourceRepository.id)
        .limit(21),
    ))
    committed_revisions = 0
    revision_failures = 0
    for repository_id in target_ids[:20]:
        try:
            branch = collect_default_branch_revision(
                session, installation=installation, repository_id=repository_id,
            )
            publish_default_branch_revision(
                session, installation=installation, evidence=branch,
            )
            committed_revisions += 1
        except (GitHubProviderError, RepositoryGenerationError):
            session.rollback()
            revision_failures += 1
    return CollectionOutcome(
        installation_id=generation.installation_id,
        generation=generation.generation,
        status='committed',
        observed_count=count,
        committed_revisions=committed_revisions,
        revision_failures=revision_failures,
        unchecked_revisions=max(len(target_ids) - 20, 0),
    )
