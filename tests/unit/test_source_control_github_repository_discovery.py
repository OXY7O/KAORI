"""SC-03 exhaustive/partial/duplicate/owner-scope repository collection."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.integrations.source_control.source_control.providers.github import repository_discovery as discovery
from app.integrations.source_control.source_control.providers.github.transport import (
    GitHubProviderError,
    InstallationToken,
)


def _repository(i: int) -> dict:
    return {
        'id': i, 'name': f'app-{i}', 'full_name': f'org/app-{i}',
        'owner': {'id': 123, 'login': 'org'}, 'default_branch': 'main',
        'archived': False, 'visibility': 'private',
    }


def _installation():
    return SimpleNamespace(
        id=1, provider_key='github', host_key='github.com',
        native_app_id='7', native_installation_id='99',
        repository_scope='selected',
        account=SimpleNamespace(native_account_id='123'),
    )


class Client:
    def __init__(self, records, *, count=None, override=None, scope='selected'):
        self.records = records
        self.count = len(records) if count is None else count
        self.override = override or {}
        self.scope = scope
        self.pages = []

    def installation_detail(self, installation_id, account_id):
        assert (installation_id, account_id) == ('99', '123')
        return {
            'id': 99, 'app_id': 7,
            'account': {'id': 123, 'type': 'Organization', 'login': 'org'},
            'repository_selection': self.scope,
        }

    def mint_installation_token(self, installation_id, *, permissions):
        assert permissions == {'metadata': 'read'}
        return InstallationToken(
            token='never-persist',
            expires_at=datetime.now(UTC) + timedelta(minutes=40),
            permissions=permissions, repository_selection=self.scope,
        )

    def repository_page(self, token, page):
        self.pages.append(page)
        if page in self.override:
            return self.override[page]
        start = (page - 1) * discovery.PAGE_SIZE
        return {
            'total_count': self.count,
            'repositories': self.records[start:start + discovery.PAGE_SIZE],
            'repository_selection': self.scope,
        }


@pytest.fixture(autouse=True)
def provider_admitted_for_pure_collector_test(monkeypatch):
    monkeypatch.setattr(
        discovery, 'provider_kind', lambda *_: SimpleNamespace(available=True)
    )


def test_multi_page_exhaustive_installation_collection():
    client = Client([_repository(i) for i in range(1, 48)])
    result = discovery.collect_installation_repositories(_installation(), client=client)
    assert result.expected_count == 47
    assert len(result.repositories) == 47
    assert result.pages == 3
    assert client.pages == [1, 2, 3]
    assert result.repository_selection == 'selected'
    assert result.repositories[0].default_branch == 'main'


def test_zero_requires_real_complete_authorized_page():
    result = discovery.collect_installation_repositories(_installation(), client=Client([]))
    assert result.expected_count == 0 and result.pages == 1


def test_partial_provider_page_does_not_yield_a_batch():
    client = Client([_repository(1)], count=3)
    with pytest.raises(GitHubProviderError, match='ended before coverage'):
        discovery.collect_installation_repositories(_installation(), client=client)


def test_changed_total_count_fails_closed():
    client = Client(
        [_repository(i) for i in range(1, 22)],
        override={2: {'total_count': 99, 'repositories': [_repository(21)]}},
    )
    with pytest.raises(GitHubProviderError, match='incomplete or inconsistent'):
        discovery.collect_installation_repositories(_installation(), client=client)


def test_duplicate_page_native_id_fails_closed():
    client = Client(
        [_repository(i) for i in range(1, 23)],
        override={2: {'total_count': 22, 'repositories': [_repository(1), _repository(22)]}},
    )
    with pytest.raises(GitHubProviderError, match='repeated a native ID'):
        discovery.collect_installation_repositories(_installation(), client=client)


def test_cross_account_owner_is_not_authorized_by_installation():
    rogue = _repository(2)
    rogue['owner']['id'] = 999
    client = Client([rogue])
    with pytest.raises(GitHubProviderError, match='does not match'):
        discovery.collect_installation_repositories(_installation(), client=client)


def test_scope_change_before_collection_denies_evidence():
    client = Client([_repository(1)], scope='all')
    with pytest.raises(GitHubProviderError, match='scope changed'):
        discovery.collect_installation_repositories(_installation(), client=client)


def test_token_expiry_or_github_network_error_cannot_publish_inventory():
    class Failing(Client):
        def repository_page(self, token, page):
            raise GitHubProviderError('GitHub installation API request was rejected or unavailable.')

    with pytest.raises(GitHubProviderError):
        discovery.collect_installation_repositories(
            _installation(), client=Failing([_repository(1)])
        )


def test_provider_planned_prevents_collection(monkeypatch):
    monkeypatch.setattr(
        discovery, 'provider_kind', lambda *_: SimpleNamespace(available=False)
    )
    with pytest.raises(GitHubProviderError, match='not admitted'):
        discovery.collect_installation_repositories(
            _installation(), client=Client([_repository(1)])
        )


def test_no_git_clone_or_file_content_ingestion():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2] /
        'app/integrations/source_control/source_control/providers/github/repository_discovery.py'
    ).read_text()
    assert 'subprocess' not in source
    assert 'git clone' not in source
    assert 'contents_url' not in source
    assert 'db.session' not in source
