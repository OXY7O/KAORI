"""SC-03 one-shot collection orchestration never publishes failed evidence."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.integrations.source_control.source_control.providers.github import repository_sync
from app.integrations.source_control.source_control.providers.github.repository_commit import (
    RepositoryGeneration, RepositoryGenerationError,
)
from app.integrations.source_control.source_control.providers.github.transport import GitHubProviderError


def _installation():
    return SimpleNamespace(id=9)


class FakeSession:
    def __init__(self):
        self.rollbacks = 0
    def rollback(self):
        self.rollbacks += 1
    def scalars(self, _statement):
        return []
    def scalar(self, _statement):
        return 0


def test_success_uses_single_generation_and_commit(monkeypatch):
    calls = []
    lease = RepositoryGeneration(installation_id=9, generation=4)
    evidence = SimpleNamespace(expected_count=3)
    monkeypatch.setattr(
        repository_sync, 'reserve_generation',
        lambda _session, _installation: calls.append('reserve') or lease,
    )
    monkeypatch.setattr(
        repository_sync, 'collect_installation_repositories',
        lambda _installation: calls.append('collect') or evidence,
    )
    monkeypatch.setattr(
        repository_sync, 'publish_generation',
        lambda _session, _installation, _lease, _evidence: calls.append('publish') or 3,
    )
    result = repository_sync.synchronize_installation(FakeSession(), _installation())
    assert calls == ['reserve', 'collect', 'publish']
    assert result.generation == 4
    assert result.observed_count == 3
    assert result.status == 'committed'


def test_partial_pagination_marks_degraded_without_commit(monkeypatch):
    lease = RepositoryGeneration(installation_id=9, generation=4)
    state = FakeSession()
    failures = []
    monkeypatch.setattr(repository_sync, 'reserve_generation', lambda *_: lease)
    monkeypatch.setattr(
        repository_sync, 'collect_installation_repositories',
        lambda *_: (_ for _ in ()).throw(GitHubProviderError('incomplete')),
    )
    monkeypatch.setattr(
        repository_sync, 'publish_generation',
        lambda *_: pytest.fail('incomplete evidence must not be published'),
    )
    monkeypatch.setattr(
        repository_sync, 'record_generation_failure',
        lambda *_: failures.append('degraded'),
    )
    with pytest.raises(GitHubProviderError):
        repository_sync.synchronize_installation(state, _installation())
    assert state.rollbacks == 1
    assert failures == ['degraded']


def test_late_scan_does_not_invalidate_newer_generation(monkeypatch):
    lease = RepositoryGeneration(installation_id=9, generation=2)
    state = FakeSession()
    statuses = []
    monkeypatch.setattr(repository_sync, 'reserve_generation', lambda *_: lease)
    monkeypatch.setattr(repository_sync, 'collect_installation_repositories', lambda *_: object())
    monkeypatch.setattr(
        repository_sync, 'publish_generation',
        lambda *_: (_ for _ in ()).throw(RepositoryGenerationError('stale')),
    )
    monkeypatch.setattr(
        repository_sync, 'record_generation_failure',
        lambda *_: statuses.append('checked'),
    )
    with pytest.raises(RepositoryGenerationError):
        repository_sync.synchronize_installation(state, _installation())
    assert statuses == ['checked']
    assert state.rollbacks == 1


def test_no_custom_celery_or_webhook_dispatcher():
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2] /
        'app/integrations/source_control/source_control/providers/github/repository_sync.py'
    ).read_text()
    assert '@shared_task' not in src
    assert 'apply_async' not in src
    assert 'send_task' not in src
    assert 'enqueue_canonical_job' not in src



def test_unexpected_publish_db_error_rolls_back_and_preserves_prior_snapshot(monkeypatch):
    lease = RepositoryGeneration(installation_id=9, generation=6)
    session = FakeSession()
    calls = []
    monkeypatch.setattr(repository_sync, 'reserve_generation', lambda *_: lease)
    monkeypatch.setattr(repository_sync, 'collect_installation_repositories', lambda *_: object())
    monkeypatch.setattr(
        repository_sync, 'publish_generation',
        lambda *_: (_ for _ in ()).throw(RuntimeError('database unavailable')),
    )
    monkeypatch.setattr(
        repository_sync, 'record_generation_failure',
        lambda *_: calls.append('mark-degraded'),
    )
    with pytest.raises(RuntimeError, match='database unavailable'):
        repository_sync.synchronize_installation(session, _installation())
    assert session.rollbacks == 1
    assert calls == ['mark-degraded']



def test_revision_gap_counts_all_unchecked_repositories(monkeypatch):
    session = FakeSession()
    session.scalar = lambda _: 225
    session.scalars = lambda _: range(1, 21)
    lease = RepositoryGeneration(installation_id=9, generation=8)
    monkeypatch.setattr(repository_sync, 'reserve_generation', lambda *_: lease)
    monkeypatch.setattr(repository_sync, 'collect_installation_repositories', lambda *_: object())
    monkeypatch.setattr(repository_sync, 'publish_generation', lambda *_: 225)
    monkeypatch.setattr(
        repository_sync, 'collect_default_branch_revision',
        lambda *_args, **_kwargs: SimpleNamespace(commit_sha='a' * 40),
    )
    monkeypatch.setattr(repository_sync, 'publish_default_branch_revision', lambda *_args, **_kwargs: True)
    result = repository_sync.synchronize_installation(session, _installation())
    assert result.committed_revisions == 20
    assert result.unchecked_revisions == 205
    assert result.revision_failures == 0


def test_branch_collect_failure_remains_partial_not_repository_rollback(monkeypatch):
    session = FakeSession()
    session.scalar = lambda _: 3
    session.scalars = lambda _: [1, 2, 3]
    lease = RepositoryGeneration(installation_id=9, generation=9)
    monkeypatch.setattr(repository_sync, 'reserve_generation', lambda *_: lease)
    monkeypatch.setattr(repository_sync, 'collect_installation_repositories', lambda *_: object())
    monkeypatch.setattr(repository_sync, 'publish_generation', lambda *_: 3)
    def branch(_session, *, installation, repository_id):
        if repository_id == 2:
            raise GitHubProviderError('branch missing')
        return SimpleNamespace(commit_sha='b' * 40)
    monkeypatch.setattr(repository_sync, 'collect_default_branch_revision', branch)
    monkeypatch.setattr(repository_sync, 'publish_default_branch_revision', lambda *_args, **_kwargs: True)
    result = repository_sync.synchronize_installation(session, _installation())
    assert result.committed_revisions == 2
    assert result.revision_failures == 1
    assert result.observed_count == 3
    assert session.rollbacks == 1
