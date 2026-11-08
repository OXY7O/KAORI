"""Read-only exact default-branch SHA with installation-bound provider authority.

SC-03 #2742. Native repository IDs and active grants come from committed
KAORI records; GitHub is rechecked before resolving owner/name and branch.
The output is not committed until separately passed to reference_commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.source_control.source_control.providers.github.credential_service import (
    build_client_for_installation,
)
from app.integrations.source_control.source_control.providers.github.repository_commit import _admitted
from app.integrations.source_control.source_control.providers.github.transport import GitHubProviderError
from app.models.source_control import SourceInstallation, SourceRepository, SourceRepositoryGrant


@dataclass(frozen=True, slots=True)
class DefaultBranchEvidence:
    repository_id: int
    native_repository_id: str
    installation_id: int
    full_ref: str
    commit_sha: str
    observed_at: datetime


def collect_default_branch_revision(
    session: Session,
    *,
    installation: SourceInstallation,
    repository_id: int,
) -> DefaultBranchEvidence:
    """Collect one authorized exact tip; never accept a user-provided URL."""
    _admitted(installation)
    if isinstance(repository_id, bool) or not isinstance(repository_id, int) or repository_id <= 0:
        raise GitHubProviderError('A committed repository identity is required.')
    repo = session.get(SourceRepository, repository_id)
    if repo is None or repo.provider_key != 'github' or repo.host_key != installation.host_key:
        raise GitHubProviderError('Source repository identity is unavailable in this installation.')
    grant = session.execute(
        select(SourceRepositoryGrant.id).where(
            SourceRepositoryGrant.installation_id == installation.id,
            SourceRepositoryGrant.repository_id == repo.id,
            SourceRepositoryGrant.access_status == 'granted',
            SourceRepositoryGrant.valid_until.is_(None),
        )
    ).scalar_one_or_none()
    if grant is None or installation.account is None or repo.account_id != installation.account.id:
        raise GitHubProviderError('Current installation-to-repository grant is not authorized.')
    if not repo.full_name or not repo.default_branch:
        raise GitHubProviderError('Default branch has not been observed.')
    owner, separator, name = repo.full_name.partition('/')
    if not separator or not owner or not name:
        raise GitHubProviderError('Committed repository path is invalid.')
    client = build_client_for_installation(installation)
    client.installation_detail(
        installation.native_installation_id,
        installation.account.native_account_id,
    )
    token = client.mint_installation_token(
        installation.native_installation_id,
        permissions={'metadata': 'read', 'contents': 'read'},
    )
    if token.repository_selection != installation.repository_scope:
        raise GitHubProviderError('Repository grant changed during default-branch collection.')
    sha = client.default_branch_tip(token, owner, name, repo.default_branch, repo.native_repository_id)
    return DefaultBranchEvidence(
        repository_id=repo.id,
        native_repository_id=repo.native_repository_id,
        installation_id=installation.id,
        full_ref=f'refs/heads/{repo.default_branch}',
        commit_sha=sha,
        observed_at=datetime.now(UTC),
    )
