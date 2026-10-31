"""SC-02 secure onboarding and permission-specific readiness contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.integrations.source_control.source_control.providers.github import readiness, registration
from app.integrations.source_control.source_control.providers.github.transport import (
    GitHubProviderError,
    InstallationReadiness,
)


def _input(**changes):
    base = dict(
        name='GitHub Prod',
        environment='production',
        description='Source provider',
        app_id='12',
        installation_id='23',
        account_id='34',
        private_key_pem='-----BEGIN PRIVATE KEY----- TEST',
        webhook_secret='test-only-secret',
    )
    return registration.GitHubConnectionInput(**{**base, **changes})


def _evidence(perms=('metadata',), scope='selected'):
    return InstallationReadiness(
        app_id=12,
        installation_id=23,
        account_id=34,
        account_type='Organization',
        repository_selection=scope,
        granted_repository_count=4,
        permission_names=perms,
        observed_at=datetime.now(UTC),
    )


def test_registration_secrets_are_omitted_from_repr():
    obj = _input()
    assert '-----BEGIN PRIVATE KEY----- TEST' not in repr(obj)
    assert 'test-only-secret' not in repr(obj)


def test_live_test_uses_only_scoped_provider(monkeypatch):
    observed = []

    class Stub:
        def __init__(self, *, app_id, private_key_pem):
            observed.append((app_id, private_key_pem))

        def validate_installation(self, installation_id, account_id):
            observed.append((installation_id, account_id))
            return _evidence()

    monkeypatch.setattr(registration, 'GitHubAppClient', Stub)
    assert registration.test_connection(_input()).installation_id == 23
    assert observed == [('12', '-----BEGIN PRIVATE KEY----- TEST'), ('23', '34')]


@pytest.mark.parametrize('name', ['', 'x', 'A' * 161, 'title\nforged'])
def test_registration_rejects_bad_names_before_network(name, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('must fail before network')

    monkeypatch.setattr(registration, 'GitHubAppClient', forbidden)
    with pytest.raises(ValueError):
        registration.test_connection(_input(name=name))


@pytest.mark.parametrize(
    'permission,status',
    [
        (('metadata',), 'validation_required'),
        (('metadata', 'contents'), 'ready'),
        (('metadata', 'contents', 'pull_requests', 'actions', 'checks', 'deployments'), 'ready'),
        (('contents',), 'blocked'),
    ],
)
def test_permission_coverage_separates_connection_readiness_from_inventory(permission, status):
    assessment = readiness.assess_installation_readiness(_evidence(perms=permission))
    assert assessment.status == status
    assert assessment.capability_states['repository_inventory'] == (
        'permission_verified' if 'metadata' in permission else 'permission_unavailable'
    )


def test_selected_grant_scope_is_not_reported_as_all_repos():
    assessment = readiness.assess_installation_readiness(_evidence())
    assert assessment.repository_scope == 'selected'
    assert assessment.coverage_hint == 'selected_repositories'


def test_unknown_grant_scope_is_denied():
    assessment = readiness.assess_installation_readiness(_evidence(scope='unknown'))
    assert assessment.status == 'blocked'
    assert assessment.capability_states == {}


def test_repository_count_does_not_imply_inventory_complete():
    assessment = readiness.assess_installation_readiness(_evidence(perms=('metadata',)))
    assert assessment.status != 'ready'
    assert assessment.capability_states['source_revision'] == 'permission_unavailable'


@pytest.mark.parametrize('environment', ['', 'prod', 'DEV', 'production '])
def test_environment_uses_approved_kaori_taxonomy(environment):
    with pytest.raises(ValueError, match='taxonomy'):
        registration.test_connection(_input(environment=environment))


@pytest.mark.parametrize('webhook_secret', ['', 'too-short', 'with\nnewline'])
def test_webhook_secret_requires_safe_length_and_characters(webhook_secret):
    with pytest.raises(GitHubProviderError):
        registration.test_connection(_input(webhook_secret=webhook_secret))


def test_secret_digest_comparison_handles_unicode_without_exposing_value():
    assert registration._same_secret('unicode-\u2603', 'unicode-\u2603')
    assert not registration._same_secret('unicode-\u2603', 'unicode-\u2602')


def test_registration_is_blocked_while_provider_is_only_planned(monkeypatch):
    def reject_network(_values):
        raise AssertionError('planned provider must fail before network or database')

    monkeypatch.setattr(registration, 'test_connection', reject_network)
    monkeypatch.setattr(
        registration,
        'provider_kind',
        lambda *_: SimpleNamespace(available=False),
    )
    with pytest.raises(GitHubProviderError, match='admission is pending'):
        registration.save_tested_connection(_input())


def test_ready_connection_does_not_claim_committed_repository_coverage():
    assessment = readiness.assess_installation_readiness(_evidence(perms=('metadata', 'contents'), scope='selected'))
    assert assessment.status == 'ready'
    assert assessment.coverage_hint == 'selected_repositories'
    assert assessment.capability_states['workflow_runs'] == 'permission_unavailable'
