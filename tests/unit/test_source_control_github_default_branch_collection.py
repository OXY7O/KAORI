"""SC-03 default branch collection requires a committed active installation grant."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.integrations.source_control.source_control.providers.github import default_branch
from app.integrations.source_control.source_control.providers.github.transport import (
    GitHubProviderError,
    InstallationToken,
)
from app.models.integration import IntegrationInstance
from app.models.source_control import (
    SourceAccount,
    SourceInstallation,
    SourceRepository,
    SourceRepositoryGrant,
)


@pytest.fixture
def authorized(monkeypatch):
    monkeypatch.setattr(default_branch, '_admitted', lambda _: None)
    engine = create_engine('sqlite+pysqlite:///:memory:')
    IntegrationInstance.metadata.create_all(bind=engine, tables=[
        IntegrationInstance.__table__,
        SourceAccount.__table__,
        SourceInstallation.__table__,
        SourceRepository.__table__,
        SourceRepositoryGrant.__table__,
    ])
    with Session(engine) as session:
        account = SourceAccount(
            provider_key='github', host_key='github.com', native_account_id='42',
        )
        canonical = IntegrationInstance(
            integration_type='source_control', provider_key='github',
            adapter_key='github_rest_v3', name='GitHub organization',
            enabled=True, lifecycle_status='active', readiness_status='validation_required',
        )
        session.add_all([account, canonical])
        session.flush()
        installation = SourceInstallation(
            integration_instance_id=canonical.id,
            provider_key='github', host_key='github.com',
            native_app_id='11', native_installation_id='22', account_id=account.id,
            repository_scope='selected',
        )
        repo = SourceRepository(
            provider_key='github', host_key='github.com',
            native_repository_id='123', name='service', full_name='org/service',
            default_branch='main', account_id=account.id,
        )
        session.add_all([installation, repo])
        session.flush()
        grant = SourceRepositoryGrant(
            installation_id=installation.id, repository_id=repo.id,
            access_status='granted', valid_from=datetime.now(UTC),
            last_observed_at=datetime.now(UTC),
        )
        session.add(grant)
        session.commit()
        yield session, installation, repo, grant
    engine.dispose()


def test_default_tip_client_receives_only_proven_scoped_identity(authorized, monkeypatch):
    session, installation, repo, _grant = authorized
    calls = []
    class Client:
        def installation_detail(self, native_install, native_account):
            calls.append(('detail', native_install, native_account))
            return {'repository_selection': 'selected'}

        def mint_installation_token(self, native_install, *, permissions):
            calls.append(('token', native_install, permissions))
            return InstallationToken(
                'ephemeral', datetime.now(UTC) + timedelta(minutes=30),
                permissions, 'selected',
            )

        def default_branch_tip(self, _token, owner, name, branch, native_id):
            calls.append(('tip', owner, name, branch, native_id))
            return 'a' * 40

    monkeypatch.setattr(default_branch, 'build_client_for_installation', lambda _i: Client())
    observation = default_branch.collect_default_branch_revision(
        session, installation=installation, repository_id=repo.id,
    )
    assert observation.full_ref == 'refs/heads/main'
    assert observation.commit_sha == 'a' * 40
    assert observation.native_repository_id == '123'
    assert calls == [
        ('detail', '22', '42'),
        ('token', '22', {'metadata': 'read', 'contents': 'read'}),
        ('tip', 'org', 'service', 'main', '123'),
    ]


def test_revoked_grant_is_denied_before_live_call(authorized, monkeypatch):
    session, installation, repo, grant = authorized
    grant.access_status = 'access_lost'
    session.flush()
    monkeypatch.setattr(
        default_branch, 'build_client_for_installation',
        lambda _: pytest.fail('revoked grant must not contact GitHub'),
    )
    with pytest.raises(GitHubProviderError, match='not authorized'):
        default_branch.collect_default_branch_revision(
            session, installation=installation, repository_id=repo.id,
        )


def test_other_installation_and_unknown_repo_are_denied(authorized, monkeypatch):
    session, installation, repo, _grant = authorized
    other = SimpleNamespace(
        id=installation.id + 500,
        host_key=installation.host_key,
        account=installation.account,
        native_installation_id=installation.native_installation_id,
        repository_scope=installation.repository_scope,
    )
    monkeypatch.setattr(
        default_branch, 'build_client_for_installation',
        lambda _: pytest.fail('unproven repository must not contact GitHub'),
    )
    with pytest.raises(GitHubProviderError):
        default_branch.collect_default_branch_revision(
            session, installation=other, repository_id=repo.id,
        )
    with pytest.raises(GitHubProviderError):
        default_branch.collect_default_branch_revision(
            session, installation=other, repository_id=99999,
        )
