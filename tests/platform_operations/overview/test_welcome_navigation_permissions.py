from __future__ import annotations

from pathlib import Path

import pytest

from app.welcome.shortcuts import (
    WELCOME_SHORTCUT_DEFINITIONS,
    resolve_welcome_target,
)


ROOT = Path(__file__).resolve().parents[3]
OVERVIEW = 'platform_operations.overview.index'


def _platform_targets():
    return next(
        definition['targets']
        for definition in WELCOME_SHORTCUT_DEFINITIONS
        if definition['title'] == 'Platform Operations'
    )


@pytest.mark.parametrize(
    ('permissions', 'allowed'),
    [
        ({'jobs.configure'}, False),
        ({'jobs.view'}, True),
        ({'jobs.configure', 'jobs.view'}, True),
        ({'platform_operations.view_data_lifecycle'}, True),
        ({'kubernetes_secrets.manage_reveal'}, True),
        (set(), False),
    ],
)
def test_welcome_shortcut_requires_actual_overview_read_access(permissions, allowed):
    target = resolve_welcome_target(_platform_targets(), permissions.__contains__)
    assert (target == OVERVIEW) is allowed


def test_shortcut_permissions_are_not_broader_than_overview_route():
    source = (ROOT / 'app/platform_operations/overview/routes.py').read_text(encoding='utf-8')
    route_permissions = {
        'jobs.view',
        'platform_operations.view_data_lifecycle',
        'kubernetes_secrets.manage_reveal',
    }
    for permission in route_permissions:
        assert f"'{permission}'" in source
    assert {permission for permission, endpoint in _platform_targets() if endpoint == OVERVIEW} == route_permissions
    assert 'jobs.configure' not in dict(_platform_targets())
