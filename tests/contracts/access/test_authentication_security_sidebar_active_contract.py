"""Authentication Security owns its Level-2 Access sidebar active state (#3181)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.common import workspace_navigation as navigation


def _active_access_child(endpoint: str, monkeypatch: pytest.MonkeyPatch) -> tuple[str, list[str]]:
    """Exercise the real server-side sidebar model with safe URL stubs."""
    monkeypatch.setattr(navigation, 'url_for', lambda target, **kwargs: f'/{target}')
    user = SimpleNamespace(is_authenticated=True, has_permission=lambda _permission: True)
    sections = navigation.build_sidebar_navigation(endpoint, user)
    active_workspaces = [
        workspace
        for section in sections
        for workspace in section['items']
        if workspace['active']
    ]
    assert len(active_workspaces) == 1
    workspace = active_workspaces[0]
    assert workspace['key'] == 'access'
    children = [child['key'] for child in workspace['children'] if child['active']]
    assert len(children) == 1, f'Expected one active Access capability for {endpoint}'
    return children[0], [child['key'] for child in workspace['children']]


@pytest.mark.parametrize(
    'endpoint',
    (
        'access.authentication_security.index',
        'access.authentication_security.save_mfa_policy',
        'access.authentication_security.save_bot_policy',
        'access.authentication_security.test_bot_provider',
    ),
)
def test_authentication_security_is_the_only_active_access_child(
    endpoint: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    active_key, visible_keys = _active_access_child(endpoint, monkeypatch)
    assert active_key == 'authentication_security'
    assert 'overview' in visible_keys
    assert 'authentication_security' in visible_keys


@pytest.mark.parametrize(
    ('endpoint', 'expected'),
    (
        ('access.overview.index', 'overview'),
        ('users.index', 'users'),
        ('identity_providers.index', 'identity_providers'),
        ('access.roles.index', 'roles'),
        ('access.permissions.index', 'permissions'),
        ('access.activity_audit.index', 'activity_audit'),
    ),
)
def test_existing_access_sidebar_capabilities_keep_their_active_state(
    endpoint: str, expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    active_key, _ = _active_access_child(endpoint, monkeypatch)
    assert active_key == expected


def test_active_highlight_requires_access_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(navigation, 'url_for', lambda target, **kwargs: f'/{target}')
    user = SimpleNamespace(
        is_authenticated=True,
        has_permission=lambda permission: permission != 'identity_providers.view',
    )
    sections = navigation.build_sidebar_navigation('access.authentication_security.index', user)
    access = next(
        workspace
        for section in sections
        for workspace in section['items']
        if workspace['key'] == 'access'
    )
    assert access['active']
    assert not any(child['key'] == 'authentication_security' for child in access['children'])
    # Do not create a second active child to compensate for an unavailable
    # permission-gated capability.
    assert not any(child['active'] for child in access['children'])
