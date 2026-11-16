"""Committed repository coverage statistics for one *already authorized* installation.

Only KAORI's retained repository/grant/reference state is queried. No GitHub
network access, cross-installation summing, or historic trend extrapolation.
The product route enforces the local UAT boundary before passing an ID.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from flask_sqlalchemy.session import Session as FlaskSession
from sqlalchemy import and_, case, func, literal, or_, select
from sqlalchemy.orm import Session, scoped_session

from app.extensions.db import db
from app.models.source_control import (
    SourceReference,
    SourceRepository,
    SourceRepositoryCollectionState,
    SourceRepositoryGrant,
    SourceRevision,
)

_MAX_ATTENTION_ROWS = 5


@dataclass(frozen=True, slots=True)
class CoverageCategory:
    label: str
    count: int
    percent: int


@dataclass(frozen=True, slots=True)
class RepositoryAttention:
    name: str
    repository_id: int
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RepositoryProfile:
    """One currently granted repository, never an installation or org total."""

    name: str
    native_id: str
    visibility: str
    lifecycle: str
    default_branch: str | None
    exact_sha: str | None
    repository_observed_at: datetime | None
    reference_observed_at: datetime | None
    access_status: str
    grant_observed_at: datetime | None
    provider_presence: str


@dataclass(frozen=True, slots=True)
class RepositoryCoverage:
    installation_id: int
    collected: bool
    collection_status: str
    observed_count: int | None
    grant_count: int | None
    grant_count_matches_observation: bool | None
    collection_coverage: str
    selection_scope: str
    committed_at: datetime | None
    visibility: tuple[CoverageCategory, ...]
    lifecycle: tuple[CoverageCategory, ...]
    references: tuple[CoverageCategory, ...]
    attention_count: int | None
    attention: tuple[RepositoryAttention, ...]
    single_repository: str | None
    single_profile: RepositoryProfile | None = None
    last_repository_observed_at: datetime | None = None
    last_reference_observed_at: datetime | None = None
    last_grant_observed_at: datetime | None = None
    collection_observed_at: datetime | None = None


def _categories(
    counts: dict[str, int],
    labels: tuple[str, ...],
    total: int,
) -> tuple[CoverageCategory, ...]:
    return tuple(
        CoverageCategory(
            label=label,
            count=counts.get(label, 0),
            percent=round(counts.get(label, 0) * 100 / total) if total else 0,
        )
        for label in labels
    )


def _coverage_attention(
    session: Session | scoped_session[Session] | scoped_session[FlaskSession],
    scoped_statement: Callable[..., Any],
    visibility_expr: Any,
    lifecycle_expr: Any,
    reference_expr: Any,
) -> list[RepositoryAttention]:
    """Bounded attention rows from the same independently authorized grants."""
    rows = session.execute(
        scoped_statement(
            SourceRepository.id,
            SourceRepository.full_name,
            SourceRepository.native_repository_id,
            visibility_expr,
            lifecycle_expr,
            reference_expr,
        )
        .where(
            or_(
                visibility_expr == 'unknown',
                lifecycle_expr == 'Unknown',
                reference_expr != 'Exact SHA',
            )
        )
        .order_by(SourceRepository.full_name, SourceRepository.id)
        .limit(_MAX_ATTENTION_ROWS)
    ).all()
    attention = []
    for repository_id, full_name, native_id, visibility, lifecycle, reference in rows:
        reasons = []
        if visibility == 'unknown':
            reasons.append('Visibility Unknown')
        if lifecycle == 'Unknown':
            reasons.append('Lifecycle Unknown')
        if reference == 'Missing Branch':
            reasons.append('Default Branch Missing')
        elif reference == 'Branch Only':
            reasons.append('Exact SHA Missing')
        attention.append(
            RepositoryAttention(
                name=full_name or f'Repository #{native_id}',
                repository_id=repository_id,
                reasons=tuple(reasons),
            )
        )
    return attention


def _single_repository_profile(
    session: Session | scoped_session[Session] | scoped_session[FlaskSession],
    scoped_statement: Callable[..., Any],
) -> RepositoryProfile:
    """Present the sole authorized repo without altering grant join semantics."""
    detail = session.execute(
        scoped_statement(
            SourceRepository.full_name,
            SourceRepository.native_repository_id,
            SourceRepository.visibility,
            SourceRepository.archived,
            SourceRepository.default_branch,
            SourceRevision.commit_sha,
            SourceRepository.last_observed_at,
            SourceReference.last_observed_at,
            SourceRepositoryGrant.access_status,
            SourceRepositoryGrant.last_observed_at,
            SourceRepository.provider_presence,
        ).limit(1)
    ).one()
    (
        full_name,
        native_id,
        visibility,
        archived,
        default_branch,
        exact_sha,
        repository_observed_at,
        reference_observed_at,
        grant_access,
        grant_observed_at,
        provider_presence,
    ) = detail
    return RepositoryProfile(
        name=full_name or f'Repository #{native_id}',
        native_id=native_id,
        visibility=(
            visibility.title()
            if visibility and visibility.lower() in {'public', 'private', 'internal'}
            else 'Unknown'
        ),
        lifecycle='Archived' if archived is True else ('Active' if archived is False else 'Unknown'),
        default_branch=default_branch or None,
        exact_sha=exact_sha,
        repository_observed_at=repository_observed_at,
        reference_observed_at=reference_observed_at,
        access_status=grant_access,
        grant_observed_at=grant_observed_at,
        provider_presence=provider_presence or 'unknown',
    )


def read_repository_coverage(
    session: Session | scoped_session[Session] | scoped_session[FlaskSession],
    *,
    authorized_installation_id: int,
) -> RepositoryCoverage:
    """Read grouped evidence for an installation *authorized by the caller*.

    An uncollected installation is UNKNOWN, not a verified empty portfolio.
    SQL groups source rows server-side, so the dashboard never loads an entire
    repository inventory into memory and has a bounded five-item attention list.
    """
    if (
        isinstance(authorized_installation_id, bool)
        or not isinstance(authorized_installation_id, int)
        or authorized_installation_id <= 0
    ):
        raise ValueError('An independently authorized installation ID is required.')

    state = session.get(SourceRepositoryCollectionState, authorized_installation_id)
    if state is None or state.committed_generation == 0:
        return RepositoryCoverage(
            installation_id=authorized_installation_id,
            collected=False,
            collection_status=state.status if state else 'not_collected',
            observed_count=None,
            grant_count=None,
            grant_count_matches_observation=None,
            collection_coverage='unknown',
            selection_scope='unknown',
            committed_at=None,
            visibility=(),
            lifecycle=(),
            references=(),
            attention_count=None,
            attention=(),
            single_repository=None,
        )

    visibility_expr = case(
        (
            func.lower(SourceRepository.visibility).in_(('public', 'private', 'internal')),
            func.lower(SourceRepository.visibility),
        ),
        else_='unknown',
    )
    lifecycle_expr = case(
        (SourceRepository.archived.is_(True), 'Archived'),
        (SourceRepository.archived.is_(False), 'Active'),
        else_='Unknown',
    )
    has_branch = SourceRepository.default_branch.is_not(None) & (SourceRepository.default_branch != '')
    reference_expr = case(
        (SourceRevision.commit_sha.is_not(None), 'Exact SHA'),
        (has_branch, 'Branch Only'),
        else_='Missing Branch',
    )
    scoped_conditions = (
        SourceRepositoryGrant.installation_id == authorized_installation_id,
        SourceRepositoryGrant.valid_until.is_(None),
    )

    def scoped_statement(*columns):
        return (
            select(*columns)
            .select_from(SourceRepositoryGrant)
            .join(SourceRepository, SourceRepositoryGrant.repository_id == SourceRepository.id)
            .outerjoin(
                SourceReference,
                and_(
                    SourceReference.repository_id == SourceRepository.id,
                    SourceReference.full_ref == (literal('refs/heads/') + SourceRepository.default_branch),
                ),
            )
            .outerjoin(
                SourceRevision,
                and_(
                    SourceRevision.id == SourceReference.current_revision_id,
                    SourceRevision.repository_id == SourceRepository.id,
                ),
            )
            .where(*scoped_conditions)
        )

    grouped = session.execute(
        scoped_statement(
            visibility_expr, lifecycle_expr, reference_expr, func.count(SourceRepositoryGrant.id)
        ).group_by(visibility_expr, lifecycle_expr, reference_expr)
    ).all()
    visibility_count = {'Public': 0, 'Private': 0, 'Internal': 0, 'Unknown': 0}
    lifecycle_count = {'Active': 0, 'Archived': 0, 'Unknown': 0}
    reference_count = {'Exact SHA': 0, 'Branch Only': 0, 'Missing Branch': 0}
    attention_count = 0
    total = 0
    for visibility, lifecycle, reference, count in grouped:
        amount = int(count)
        visibility_label = visibility.title() if visibility != 'unknown' else 'Unknown'
        visibility_count[visibility_label] += amount
        lifecycle_count[lifecycle] += amount
        reference_count[reference] += amount
        total += amount
        if visibility_label == 'Unknown' or lifecycle == 'Unknown' or reference != 'Exact SHA':
            attention_count += amount

    attention = _coverage_attention(
        session, scoped_statement, visibility_expr, lifecycle_expr, reference_expr
    )

    observed_times = session.execute(
        scoped_statement(
            func.max(SourceRepository.last_observed_at),
            func.max(SourceReference.last_observed_at),
            func.max(SourceRepositoryGrant.last_observed_at),
        )
    ).one()

    single_profile = _single_repository_profile(session, scoped_statement) if total == 1 else None

    return RepositoryCoverage(
        installation_id=authorized_installation_id,
        collected=True,
        collection_status=state.status,
        observed_count=state.observed_count,
        grant_count=total,
        grant_count_matches_observation=state.observed_count == total if state.observed_count is not None else None,
        collection_coverage=state.coverage,
        selection_scope=state.repository_scope,
        committed_at=state.last_committed_at,
        visibility=_categories(visibility_count, ('Public', 'Private', 'Internal', 'Unknown'), total),
        lifecycle=_categories(lifecycle_count, ('Active', 'Archived', 'Unknown'), total),
        references=_categories(reference_count, ('Exact SHA', 'Branch Only', 'Missing Branch'), total),
        attention_count=attention_count,
        attention=tuple(attention),
        single_repository=single_profile.name if single_profile else None,
        single_profile=single_profile,
        last_repository_observed_at=observed_times[0],
        last_reference_observed_at=observed_times[1],
        last_grant_observed_at=observed_times[2],
        collection_observed_at=state.last_observed_at,
    )


def read_repository_coverage_for_current_session(*, authorized_installation_id: int) -> RepositoryCoverage:
    """Only call after resolving the installation against authorized scope."""
    return read_repository_coverage(db.session, authorized_installation_id=authorized_installation_id)
