from __future__ import annotations

import pytest

from app.integrations.provider_matrix import provider_kind, provider_options
from app.integrations.taxonomy import get_capability_definition, get_domain_definition
from app.source_control.identity import (
    SourceAccountIdentity,
    SourceHost,
    SourceInstallationIdentity,
    SourceReferenceIdentity,
    SourceRepositoryIdentity,
    SourceRevisionIdentity,
)


def test_source_control_taxonomy_and_provider_matrix_agree() -> None:
    domain = get_domain_definition('source_control')
    capability = get_capability_definition('source_control', 'source_control')
    github = provider_kind('source_control', 'github')
    assert domain.label == 'Source Control'
    assert capability.domain_key == 'source_control'
    assert github.lifecycle in {'planned', 'available'}
    assert github.available == (github.lifecycle == 'available')
    assert bool(provider_options('source_control')) == github.available


def test_repository_native_id_not_mutable_owner_name_or_installation() -> None:
    host = SourceHost('GitHub', 'GitHub.com')
    repository = SourceRepositoryIdentity(host, '00042')
    another_account = SourceAccountIdentity(host, 42)
    installation = SourceInstallationIdentity(host, 123, 456)
    assert repository.key == ('github', 'github.com', 'repository', '42')
    assert another_account.key == ('github', 'github.com', 'account', '42')
    assert another_account.key != repository.key
    assert installation.key == ('github', 'github.com', 'installation', '123', '456')


def test_same_numeric_id_across_hosts_is_not_same_repository() -> None:
    cloud = SourceRepositoryIdentity(SourceHost('github', 'github.com'), 10)
    future_host = SourceRepositoryIdentity(SourceHost('github', 'ghes.example.internal'), 10)
    assert cloud != future_host
    assert cloud.key != future_host.key


def test_installation_grant_is_qualified_by_app_and_host() -> None:
    host = SourceHost('github', 'github.com')
    assert SourceInstallationIdentity(host, 12, 45) != SourceInstallationIdentity(host, 13, 45)


@pytest.mark.parametrize('invalid', [0, -1, True, 'abc', '1e3', ''])
def test_native_id_requires_positive_numeric_provider_id(invalid: object) -> None:
    with pytest.raises(ValueError):
        SourceRepositoryIdentity(SourceHost('github', 'github.com'), invalid)  # type: ignore[arg-type]


@pytest.mark.parametrize('invalid', ['https://github.com', 'github.com/abc', 'github.com@evil', 'github..com', ''])
def test_hosts_do_not_accept_origin_paths_or_credentials(invalid: str) -> None:
    with pytest.raises(ValueError):
        SourceHost('github', invalid)


def test_exact_revision_is_repository_scoped_and_does_not_depend_on_branch() -> None:
    host = SourceHost('github', 'github.com')
    sha = 'a' * 40
    first = SourceRevisionIdentity(SourceRepositoryIdentity(host, 10), sha.upper())
    second = SourceRevisionIdentity(SourceRepositoryIdentity(host, 11), sha)
    assert first.commit_sha == sha
    assert first != second
    assert first.key != second.key


@pytest.mark.parametrize('invalid', ['123abcd', 'z' * 40, ''])
def test_revision_rejects_abbreviated_or_nonhex_sha(invalid: str) -> None:
    with pytest.raises(ValueError):
        SourceRevisionIdentity(SourceRepositoryIdentity(SourceHost('github', 'github.com'), 7), invalid)


def test_reference_identity_separates_mutable_branch_and_tag() -> None:
    repo = SourceRepositoryIdentity(SourceHost('github', 'github.com'), 77)
    branch = SourceReferenceIdentity(repo, 'refs/heads/main')
    tag = SourceReferenceIdentity(repo, 'refs/tags/main')
    assert branch.key != tag.key
    with pytest.raises(ValueError):
        SourceReferenceIdentity(repo, 'main')
