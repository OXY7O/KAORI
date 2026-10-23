"""Committed read projection for installation-scoped Source Control inventory.

SC-03 #2742. The caller MUST resolve an authorized installation through
KAORI's #724 resource-scoped policy *before* invoking this function.
No GitHub API, provider token, websocket, or lazy network lookup occurs here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.source_control import (
    SourceRepository,
    SourceRepositoryCollectionState,
    SourceRepositoryGrant,
    SourceReference,
    SourceRevision,
)

_ALLOWED_PAGE_SIZES = (5, 10, 25, 50)


@dataclass(frozen=True, slots=True)
class InventoryRow:
    repository_id: int
    native_id: str
    full_name: str | None
    default_branch: str | None
    visibility: str | None
    archived: bool | None
    access_status: str
    observed_at: datetime | None
    exact_default_branch_sha: str | None
    revision_observed_at: datetime | None


@dataclass(frozen=True, slots=True)
class InventoryPage:
    installation_id: int
    collection_status: str
    coverage: str
    selection_scope: str
    collected_at: datetime | None
    observed_count: int | None
    rows: tuple[InventoryRow, ...]
    total: int | None
    page: int
    per_page: int


def read_installation_inventory(
    session: Session,
    *,
    authorized_installation_id: int,
    page: int = 1,
    per_page: int = 5,
) -> InventoryPage:
    """Never silently broadens scope to all installations/accounts.

    Pagination totals count visible committed grant relationships, not all
    provider repositories nor all repositories in the account.
    Without a successful complete generation, total/counts are UNKNOWN.
    """
    if (
        isinstance(authorized_installation_id, bool)
        or not isinstance(authorized_installation_id, int)
        or authorized_installation_id <= 0
    ):
        raise ValueError('A separately authorized installation ID is required.')
    if isinstance(page, bool) or not isinstance(page, int) or page <= 0:
        raise ValueError('Source Control inventory page must be positive.')
    if per_page not in _ALLOWED_PAGE_SIZES or isinstance(per_page, bool):
        raise ValueError('Source Control inventory pagination uses standard KAORI page sizes.')

    state = session.get(SourceRepositoryCollectionState, authorized_installation_id)
    if state is None or state.committed_generation == 0:
        return InventoryPage(
            installation_id=authorized_installation_id,
            collection_status='not_collected' if state is None else state.status,
            coverage='unknown', selection_scope='unknown',
            collected_at=None, observed_count=None, rows=(), total=None,
            page=page, per_page=per_page,
        )

    scoped = (
        select(
            SourceRepository, SourceRepositoryGrant.access_status,
            SourceRevision.commit_sha, SourceReference.last_observed_at,
        )
        .join(
            SourceRepositoryGrant,
            SourceRepositoryGrant.repository_id == SourceRepository.id,
        )
        .outerjoin(
            SourceReference,
            and_(
                SourceReference.repository_id == SourceRepository.id,
                SourceReference.full_ref == ('refs/heads/' + SourceRepository.default_branch),
            ),
        )
        .outerjoin(
            SourceRevision,
            and_(
                SourceRevision.id == SourceReference.current_revision_id,
                SourceRevision.repository_id == SourceRepository.id,
            ),
        )
        .where(
            SourceRepositoryGrant.installation_id == authorized_installation_id,
            SourceRepositoryGrant.valid_until.is_(None),
        )
    )
    count_query = (
        select(func.count())
        .select_from(SourceRepositoryGrant)
        .where(
            SourceRepositoryGrant.installation_id == authorized_installation_id,
            SourceRepositoryGrant.valid_until.is_(None),
        )
    )
    total = int(session.execute(count_query).scalar_one())
    data = session.execute(
        scoped.order_by(SourceRepository.full_name, SourceRepository.id)
        .limit(per_page).offset((page - 1) * per_page)
    ).all()
    return InventoryPage(
        installation_id=authorized_installation_id,
        collection_status=state.status,
        coverage=state.coverage,
        selection_scope=state.repository_scope,
        collected_at=state.last_committed_at,
        observed_count=state.observed_count,
        total=total,
        rows=tuple(
            InventoryRow(
                repository_id=repository.id,
                native_id=repository.native_repository_id,
                full_name=repository.full_name,
                default_branch=repository.default_branch,
                visibility=repository.visibility,
                archived=repository.archived,
                access_status=str(status),
                observed_at=repository.last_observed_at,
                exact_default_branch_sha=sha,
                revision_observed_at=tip_observed_at,
            )
            for repository, status, sha, tip_observed_at in data
        ),
        page=page, per_page=per_page,
    )
