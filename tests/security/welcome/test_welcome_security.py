from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[3]
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

    spec = importlib.util.spec_from_file_location('kaori_welcome_shortcuts_security', SHORTCUTS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _flatten(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [shortcut for group in groups for shortcut in group['shortcuts']]


def test_unauthorized_workspace_metadata_is_not_emitted(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_shortcuts(monkeypatch, {'inventory.view'})

    shortcuts = _flatten(module.build_welcome_workspace_groups())
    titles = {shortcut['title'] for shortcut in shortcuts}
    search_text = ' '.join(shortcut['search_text'] for shortcut in shortcuts)

    assert titles == {'K8s Inventory', 'Settings'}
    assert 'Dashboards' not in titles
    assert 'Reports' not in titles
    assert 'dashboard.view' not in search_text
    assert 'reports.view' not in search_text


def test_only_personal_settings_is_universal_for_authenticated_users(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_shortcuts(monkeypatch, set())

    universal_targets = [
        (definition['title'], endpoint)
        for definition in module.WELCOME_SHORTCUT_DEFINITIONS
        for permission_key, endpoint in definition['targets']
        if permission_key is None
    ]

    assert universal_targets == [('Settings', 'settings.account')]


def test_welcome_browser_filter_has_no_capability_network_discovery() -> None:
    script = (ROOT / 'app/static/js/welcome.js').read_text(encoding='utf-8')

    for network_api in ('fetch(', 'XMLHttpRequest', 'axios.', 'htmx.ajax', 'WebSocket('):
        assert network_api not in script
    assert "querySelectorAll('[data-workspace-card]')" in script
    assert 'card.hidden = !matches' in script
