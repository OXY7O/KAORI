from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
SESSION_PATH = ROOT / 'app/auth/session.py'


def _load_session(monkeypatch: pytest.MonkeyPatch):
    flask_module = ModuleType('flask')
    flask_module.current_app = SimpleNamespace(config={})  # type: ignore[attr-defined]
    flask_module.session = {}  # type: ignore[attr-defined]

    flask_login_module = ModuleType('flask_login')
    flask_login_module.login_user = lambda *_args, **_kwargs: True  # type: ignore[attr-defined]

    user_module = ModuleType('app.models.user')
    user_module.User = object  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, 'flask', flask_module)
    monkeypatch.setitem(sys.modules, 'flask_login', flask_login_module)
    monkeypatch.setitem(sys.modules, 'app.models.user', user_module)

    spec = importlib.util.spec_from_file_location('kaori_auth_session_unit', SESSION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, flask_module.session


def test_safe_next_url_accepts_only_internal_absolute_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    module, _session = _load_session(monkeypatch)

    assert module.safe_next_url('/welcome') == '/welcome'
    assert module.safe_next_url('/inventory?scope=cluster') == '/inventory?scope=cluster'
    assert module.safe_next_url('https://example.invalid') is None
    assert module.safe_next_url('//example.invalid/path') is None
    assert module.safe_next_url('/\\example.invalid') is None


def test_authenticated_identifier_parser_requires_positive_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    module, _session = _load_session(monkeypatch)

    assert module.parse_authenticated_user_identifier('7') == (7, None)
    assert module.parse_authenticated_user_identifier('7:3') == (7, 3)
    with pytest.raises(ValueError):
        module.parse_authenticated_user_identifier('7:0')
    with pytest.raises(ValueError):
        module.parse_authenticated_user_identifier('0:1')


def test_session_cleanup_preserves_remember_cookie_revocation(monkeypatch: pytest.MonkeyPatch) -> None:
    module, session = _load_session(monkeypatch)
    session.update({'_remember': 'clear', '_user_id': '7:3', 'auth_source': 'database'})

    module.clear_authenticated_session()

    assert session == {'_remember': 'clear'}
