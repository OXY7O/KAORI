"""SC-02 secure onboarding and permission-specific readiness contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.integrations.source_control.source_control.providers.github import registration, readiness
from app.integrations.source_control.source_control.providers.github.transport import InstallationReadiness


def _input(**changes):
    base = dict(
        name='GitHub Prod', environment='production', description='Source provider',
        app_id='12', installation_id='23', account_id='34',
        private_key_pem='PEM test only', webhook_secret='test-only-secret',
    )
    return registration.GitHubConnectionInput(**{**base, **changes})


def _evidence(perms=('metadata',), scope='selected'):
    return InstallationReadiness(
        app_id=12, installation_id=23, account_id=34, account_type='Organization',
        repository_selection=scope, granted_repository_count=4,
        permission_names=perms, observed_at=datetime.now(UTC),
    )


def test_registration_secrets_are_omitted_from_repr():
    obj = _input()
    assert 'PEM test only' not in repr(obj)
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
    assert observed == [('12', 'PEM test only'), ('23', '34')]


@pytest.mark.parametrize('name', ['', 'x', 'A' * 161, 'title\nforged'])
def test_registration_rejects_bad_names_before_network(name, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('must fail before network')
    monkeypatch.setattr(registration, 'GitHubAppClient', forbidden)
    with pytest.raises(ValueError):
        registration.test_connection(_input(name=name))


@pytest.mark.parametrize('permission,status', [
    (('metadata',), 'validation_required'),
    (('metadata', 'contents', 'pull_requests', 'actions', 'checks', 'deployments'), 'validation_required'),
    (('contents',), 'blocked'),
])
def test_permission_coverage_never_fabricates_ready(permission, status):
    assessment = readiness.assess_installation_readiness(_evidence(perms=permission))
    assert assessment.status == status
    assert 'ready' not in assessment.status
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
