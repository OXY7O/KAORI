"""Bounded orchestration of one authorized source-repository collection attempt.

This is an inert worker-callable service, NOT a second scheduler or Celery
task. The SC-03 authoritative worker and canonical JobExecution dispatcher
must be separately admitted before calling this in production.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

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
from app.models.source_control import SourceInstallation


@dataclass(frozen=True, slots=True)
class CollectionOutcome:
    installation_id: int
    generation: int
    status: str
    observed_count: int | None


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
    except GitHubProviderError:
        session.rollback()
        record_generation_failure(session, installation, generation)
        raise
    try:
        count = publish_generation(session, installation, generation, evidence)
    except RepositoryGenerationError:
        session.rollback()
        # A newer reservation or collection always wins. Never mark its
        # collection state as failed from this stale worker attempt.
        record_generation_failure(session, installation, generation)
        raise
    return CollectionOutcome(
        installation_id=generation.installation_id,
        generation=generation.generation,
        status='committed',
        observed_count=count,
    )
