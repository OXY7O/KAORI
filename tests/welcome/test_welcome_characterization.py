from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SHORTCUTS_PATH = ROOT / 'app/welcome/shortcuts.py'


class _User:
    def __init__(self, permissions: set[str]) -> None:
        self.permissions = permissions

    def has_permission(self, permission_key: str) -> bool:
        return permission_key in self.permissions


def _load_shortcuts(monkeypatch: pytest.MonkeyPatch, permissions: set[str]):
    flask_module = ModuleType('flask')
    flask_module.url_for = lambda endpoint: f'/endpoint/{endpoint}'  # type: ignore[attr-defined]

    flask_login_module = ModuleType('flask_login')
    flask_login_module.current_user = _User(permissions)  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, 'flask', flask_module)
    monkeypatch.setitem(sys.modules, 'flask_login', flask_login_module)

    spec = importlib.util.spec_from_file_location('kaori_welcome_shortcuts_characterization', SHORTCUTS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _flatten(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [shortcut for group in groups for shortcut in group['shortcuts']]


def test_authenticated_user_without_domain_permissions_only_sees_universal_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_shortcuts(monkeypatch, set())

    groups = module.build_welcome_workspace_groups()
    shortcuts = _flatten(groups)

    assert [group['key'] for group in groups] == ['platform']
    assert [shortcut['title'] for shortcut in shortcuts] == ['Settings']
    assert shortcuts[0]['href'] == '/endpoint/settings.account'
    assert groups[0]['shortcut_count'] == 1


def test_workspace_catalog_only_renders_authorized_destinations(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_shortcuts(monkeypatch, {'inventory.view', 'reports.view'})

    groups = module.build_welcome_workspace_groups()
    shortcuts = _flatten(groups)
    titles = [shortcut['title'] for shortcut in shortcuts]

    assert titles == ['K8s Inventory', 'Reports', 'Settings']
    assert 'Dashboards' not in titles
    assert 'Access' not in titles
    assert all('permission' not in shortcut['search_text'] for shortcut in shortcuts)


def test_workspace_with_multiple_targets_uses_first_authorized_target(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_shortcuts(monkeypatch, {'reports.manage_storage'})

    shortcuts = _flatten(module.build_welcome_workspace_groups())
    reports = next(shortcut for shortcut in shortcuts if shortcut['title'] == 'Reports')

    assert reports['href'] == '/endpoint/reports.storage'


def test_workspace_catalog_deduplicates_multi_permission_workspace_and_keeps_group_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_shortcuts(
        monkeypatch,
        {
            'jobs.view',
            'jobs.configure',
            'platform_operations.view_data_lifecycle',
            'kubernetes_secrets.manage_reveal',
        },
    )

    groups = module.build_welcome_workspace_groups()
    shortcuts = _flatten(groups)
    platform_operations = [shortcut for shortcut in shortcuts if shortcut['title'] == 'Platform Operations']
    operations_group = next(group for group in groups if group['key'] == 'operations')

    assert len(platform_operations) == 1
    assert platform_operations[0]['href'] == '/endpoint/platform_operations.overview.index'
    assert operations_group['shortcut_count'] == 1
    assert [shortcut['title'] for shortcut in operations_group['shortcuts']] == ['Platform Operations']
