from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[3]
SHORTCUTS_PATH = ROOT / 'app/welcome/shortcuts.py'


@pytest.fixture()
def shortcuts_module(monkeypatch: pytest.MonkeyPatch):
    flask_module = ModuleType('flask')
    flask_module.url_for = lambda endpoint: f'/endpoint/{endpoint}'  # type: ignore[attr-defined]
    flask_login_module = ModuleType('flask_login')
    flask_login_module.current_user = object()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, 'flask', flask_module)
    monkeypatch.setitem(sys.modules, 'flask_login', flask_login_module)

    spec = importlib.util.spec_from_file_location('kaori_welcome_target_unit', SHORTCUTS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resolver_returns_first_authorized_target(shortcuts_module) -> None:
    targets = (('reports.view', 'reports.overview'), ('reports.manage_storage', 'reports.storage'))

    resolved = shortcuts_module.resolve_welcome_target(
        targets,
        lambda permission: permission == 'reports.manage_storage',
    )

    assert resolved == 'reports.storage'


def test_resolver_returns_universal_target_without_permission_check(shortcuts_module) -> None:
    checked: list[str] = []

    resolved = shortcuts_module.resolve_welcome_target(
        ((None, 'settings.account'),),
        lambda permission: checked.append(permission) or False,
    )

    assert resolved == 'settings.account'
    assert checked == []


def test_resolver_returns_none_when_no_target_is_authorized(shortcuts_module) -> None:
    resolved = shortcuts_module.resolve_welcome_target(
        (('dashboard.view', 'kubernetes_dashboard.index'),),
        lambda _permission: False,
    )

    assert resolved is None
