"""Canonical, provider-native Source Control identities (architecture #559; SC-01 #2740).

These are immutable identifiers, not provider API clients or authorization grants.
GitHub App authentication and committed inventory arrive in SC-02/SC-03.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


_HOST_LABEL = re.compile(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?')
_FULL_COMMIT_SHA = re.compile(r'[0-9a-f]{40,128}')


def _provider_id(value: str | int) -> str:
    if isinstance(value, bool):
        raise ValueError('Provider-native identity must be a positive integer.')
    candidate = str(value).strip()
    if not candidate.isascii() or not candidate.isdecimal() or int(candidate) <= 0:
        raise ValueError('Provider-native identity must be a positive integer.')
    return str(int(candidate))


@dataclass(frozen=True, slots=True)
class SourceHost:
    """Host-qualified provider namespace, independent of an API connection."""

    provider_key: str
    host_key: str

    def __post_init__(self) -> None:
        provider = str(self.provider_key).strip().lower()
        host = str(self.host_key).strip().lower().rstrip('.')
        labels = host.split('.')
        if provider != 'github':
            raise ValueError('GitHub is the only Source Control provider qualified for this phase.')
        if (
            not host
            or len(host) > 253
            or any(len(label) > 63 or _HOST_LABEL.fullmatch(label) is None for label in labels)
        ):
            raise ValueError('Source host must be a DNS host without origin, path, or credentials.')
        object.__setattr__(self, 'provider_key', provider)
        object.__setattr__(self, 'host_key', host)

    @property
    def key(self) -> tuple[str, str]:
        return (self.provider_key, self.host_key)


@dataclass(frozen=True, slots=True)
class SourceInstallationIdentity:
    """A GitHub App grant: distinct from account, connection and repository."""

    host: SourceHost
    app_native_id: str | int
    installation_native_id: str | int

    def __post_init__(self) -> None:
        object.__setattr__(self, 'app_native_id', _provider_id(self.app_native_id))
        object.__setattr__(self, 'installation_native_id', _provider_id(self.installation_native_id))

    @property
    def key(self) -> tuple[str, str, str, str, str]:
        return (*self.host.key, 'installation', str(self.app_native_id), str(self.installation_native_id))


@dataclass(frozen=True, slots=True)
class SourceAccountIdentity:
    """Account identity is independent of mutable login and App installation."""

    host: SourceHost
    account_native_id: str | int

    def __post_init__(self) -> None:
        object.__setattr__(self, 'account_native_id', _provider_id(self.account_native_id))

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (*self.host.key, 'account', str(self.account_native_id))


@dataclass(frozen=True, slots=True)
class SourceRepositoryIdentity:
    """Stable native repository identity; owner/name/URL are mutable attributes."""

    host: SourceHost
    repository_native_id: str | int

    def __post_init__(self) -> None:
        object.__setattr__(self, 'repository_native_id', _provider_id(self.repository_native_id))

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (*self.host.key, 'repository', str(self.repository_native_id))


@dataclass(frozen=True, slots=True)
class SourceRevisionIdentity:
    """Exact source revision scoped to its canonical Repository identity."""

    repository: SourceRepositoryIdentity
    commit_sha: str

    def __post_init__(self) -> None:
        sha = str(self.commit_sha).strip().lower()
        if _FULL_COMMIT_SHA.fullmatch(sha) is None:
            raise ValueError('Source revision requires a full hexadecimal commit SHA.')
        object.__setattr__(self, 'commit_sha', sha)

    @property
    def key(self) -> tuple[str, str, str, str, str, str]:
        return (*self.repository.key, 'revision', self.commit_sha)


@dataclass(frozen=True, slots=True)
class SourceReferenceIdentity:
    """A mutable branch or tag reference, not an immutable SourceRevision."""

    repository: SourceRepositoryIdentity
    full_ref: str

    def __post_init__(self) -> None:
        ref = str(self.full_ref).strip()
        if not (
            ref.startswith('refs/heads/') and len(ref) > len('refs/heads/')
            or ref.startswith('refs/tags/') and len(ref) > len('refs/tags/')
        ):
            raise ValueError('Source reference must be a full branch or tag ref.')
        if any(char.isspace() for char in ref):
            raise ValueError('Source reference must not contain whitespace.')
        object.__setattr__(self, 'full_ref', ref)

    @property
    def key(self) -> tuple[str, str, str, str, str, str]:
        return (*self.repository.key, 'reference', self.full_ref)
