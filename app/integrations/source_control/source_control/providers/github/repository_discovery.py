"""Read-only complete installation-scoped GitHub repository discovery (#2742).

GitHub remains the native source of grants and repository ownership.
Only exhaustive, consistent, authorized pages can produce a complete batch.
A failed/inconsistent scan must not mutate committed inventory or infer absence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil
from typing import Any

from app.integrations.provider_matrix import provider_kind
from app.integrations.source_control.source_control.providers.github.credential_service import (
    build_client_for_installation,
)
from app.integrations.source_control.source_control.providers.github.transport import (
    GitHubAppClient,
    GitHubProviderError,
)
from app.models.source_control import SourceInstallation

PAGE_SIZE = 20
MAX_PAGES = 200


@dataclass(frozen=True, slots=True)
class RepositoryObservation:
    native_id: str
    owner_native_id: str
    owner_login: str
    name: str
    full_name: str
    default_branch: str | None
    visibility: str | None
    archived: bool | None


@dataclass(frozen=True, slots=True)
class RepositoryCollection:
    provider_key: str
    host_key: str
    app_native_id: str
    installation_native_id: str
    account_native_id: str
    account_type: str
    account_login: str
    repository_selection: str
    expected_count: int
    repositories: tuple[RepositoryObservation, ...]
    observed_at: datetime
    pages: int


def _native_id(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise GitHubProviderError('GitHub repository native identity is invalid.')
    return str(value)


def _bounded_name(value: Any, limit: int) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= limit or any(
        ord(char) < 32 or ord(char) == 127 for char in value
    ):
        raise GitHubProviderError('GitHub repository naming evidence is malformed.')
    return value


def _parse_repository(raw: Any, account_native_id: str) -> RepositoryObservation:
    if not isinstance(raw, dict):
        raise GitHubProviderError('GitHub repository collection contains a non-object.')
    owner = raw.get('owner')
    if not isinstance(owner, dict):
        raise GitHubProviderError('GitHub repository owner identity is missing.')
    native_id = _native_id(raw.get('id'))
    owner_id = _native_id(owner.get('id'))
    if owner_id != account_native_id:
        # One installation belongs to one account. A repository transfer
        # requires a separately verified grant; never silently reassign it.
        raise GitHubProviderError('GitHub repository owner does not match the installation account.')
    name = _bounded_name(raw.get('name'), 255)
    login = _bounded_name(owner.get('login'), 255)
    full_name = _bounded_name(raw.get('full_name'), 600)
    if full_name != f'{login}/{name}':
        raise GitHubProviderError('GitHub repository full name does not match native owner evidence.')
    branch = raw.get('default_branch')
    if branch is not None:
        branch = _bounded_name(branch, 512)
    visibility = raw.get('visibility')
    if visibility is not None and visibility not in ('public', 'private', 'internal'):
        raise GitHubProviderError('GitHub repository visibility evidence is unsupported.')
    archived = raw.get('archived')
    if archived is not None and not isinstance(archived, bool):
        raise GitHubProviderError('GitHub repository archive status is malformed.')
    return RepositoryObservation(
        native_id=native_id, owner_native_id=owner_id, owner_login=login,
        name=name, full_name=full_name, default_branch=branch,
        visibility=visibility, archived=archived,
    )


def _validate_page(raw: dict[str, Any], expected: int | None) -> tuple[int, list[Any]]:
    count = raw.get('total_count')
    records = raw.get('repositories')
    if (
        isinstance(count, bool) or not isinstance(count, int) or count < 0
        or (expected is not None and count != expected)
        or not isinstance(records, list) or len(records) > PAGE_SIZE
    ):
        raise GitHubProviderError('GitHub installation repository pagination is incomplete or inconsistent.')
    return count, records


def collect_installation_repositories(
    installation: SourceInstallation,
    *,
    client: GitHubAppClient | None = None,
) -> RepositoryCollection:
    """Discover complete authorized grant scope; no DB writes or fake zeroes.

    The caller is responsible for reserving a generation before the network
    scan and must commit only if that generation is still current.
    """
    if not provider_kind('source_control', 'github').available:
        raise GitHubProviderError('GitHub repository collection is not admitted.')
    if installation.account is None or installation.id is None:
        raise GitHubProviderError('GitHub installation account has no committed identity.')
    client = client or build_client_for_installation(installation)
    account_native_id = installation.account.native_account_id
    detail = client.installation_detail(
        installation.native_installation_id, account_native_id
    )
    account = detail['account']
    scope = detail['repository_selection']
    if scope != installation.repository_scope:
        raise GitHubProviderError('GitHub installation grant scope changed; revalidate before sync.')

    token = client.mint_installation_token(
        installation.native_installation_id,
        permissions={'metadata': 'read'},
    )
    if token.repository_selection != scope:
        raise GitHubProviderError('GitHub App token repository scope differs from the verified grant.')

    expected: int | None = None
    records: list[RepositoryObservation] = []
    seen: set[str] = set()
    pages = 0
    # Never infer an empty authorized scope from a missing page.
    for page in range(1, MAX_PAGES + 1):
        result = client.repository_page(token, page)
        count, raw_records = _validate_page(result, expected)
        if expected is None:
            expected = count
            if ceil(count / PAGE_SIZE) > MAX_PAGES:
                raise GitHubProviderError('GitHub repository inventory exceeds the approved collection bound.')
        selection = result.get('repository_selection')
        if selection is not None and selection != scope:
            raise GitHubProviderError('GitHub installation repository selection changed during pagination.')
        if len(records) + len(raw_records) > count:
            raise GitHubProviderError('GitHub repository count exceeds provider-reported coverage.')
        for raw in raw_records:
            observation = _parse_repository(raw, str(account_native_id))
            if observation.native_id in seen:
                raise GitHubProviderError('GitHub installation repository pagination repeated a native ID.')
            seen.add(observation.native_id)
            records.append(observation)
        pages = page
        if len(records) == count:
            break
        if not raw_records:
            raise GitHubProviderError('GitHub installation repository pagination ended before coverage completed.')
    if expected is None or len(records) != expected:
        raise GitHubProviderError('GitHub installation repository coverage is not exhaustive.')

    # Recheck grant and App authorization *after* pagination. Changes during
    # the scan cannot safely close previously committed selected grants.
    final = client.installation_detail(installation.native_installation_id, account_native_id)
    if final['repository_selection'] != scope or final['account']['id'] != int(account_native_id):
        raise GitHubProviderError('GitHub installation grant changed during repository discovery.')

    return RepositoryCollection(
        provider_key=installation.provider_key,
        host_key=installation.host_key,
        app_native_id=str(installation.native_app_id),
        installation_native_id=str(installation.native_installation_id),
        account_native_id=str(account_native_id),
        account_type=str(account.get('type') or 'unknown')[:30],
        account_login=_bounded_name(account.get('login'), 255),
        repository_selection=scope,
        expected_count=expected,
        repositories=tuple(records),
        observed_at=datetime.now(UTC),
        pages=pages,
    )
