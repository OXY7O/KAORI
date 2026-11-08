"""JIT projection never admits administrator-level defaults at configuration time."""

import re
from types import SimpleNamespace

from app.access.identity_providers import service


def test_jit_admin_role_is_rejected_even_for_local_break_glass(monkeypatch) -> None:
    role = SimpleNamespace(id=9, is_active=True, is_admin_level=True)
    monkeypatch.setattr(
        service,
        'db',
        SimpleNamespace(session=SimpleNamespace(get=lambda model, identity: role)),
    )
    monkeypatch.setattr(service, 'role_is_access_admin_level', lambda item: item.is_admin_level)
    monkeypatch.setattr(service, 'role_is_delegable_by_actor', lambda actor, item: True)
    actor = SimpleNamespace(auth_source='database', is_super_admin=True)

    assert (
        service.provider_default_role_assignment_error(actor, 9, jit_enabled=True)
        == 'JIT requires an active non-admin default role.'
    )
    # Non-JIT configuration remains governed by ordinary delegation rules.
    assert service.provider_default_role_assignment_error(actor, 9, jit_enabled=False) is None


def test_jit_accepts_only_active_delegable_nonadmin_role(monkeypatch) -> None:
    role = SimpleNamespace(id=7, is_active=True, is_admin_level=False)
    monkeypatch.setattr(service, 'db', SimpleNamespace(session=SimpleNamespace(get=lambda *_: role)))
    monkeypatch.setattr(service, 'role_is_access_admin_level', lambda item: item.is_admin_level)
    monkeypatch.setattr(service, 'role_is_delegable_by_actor', lambda actor, item: True)

    assert service.provider_default_role_assignment_error(object(), 7, jit_enabled=True) is None
    role.is_active = False
    assert (
        service.provider_default_role_assignment_error(object(), 7, jit_enabled=True)
        == 'The selected JIT default role is unavailable.'
    )


def test_create_edit_and_connection_test_apply_jit_save_boundary() -> None:
    from pathlib import Path

    routes = (Path(__file__).resolve().parents[3] / 'app/access/identity_providers/routes.py').read_text(
        encoding='utf-8'
    )
    guard = (
        r'provider_default_role_assignment_error\(\s*'
        r'actor,\s*form\.default_role_id\.data,\s*'
        r'jit_enabled=bool\(form\.jit_enabled\.data\)\s*\)'
    )
    assert len(re.findall(guard, routes)) == 3
