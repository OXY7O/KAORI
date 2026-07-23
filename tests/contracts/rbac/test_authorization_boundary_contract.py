from __future__ import annotations

from pathlib import Path


def test_persisted_inactive_roles_do_not_fall_back_to_default_permissions() -> None:
    source = Path('app/models/user.py').read_text(encoding='utf-8')

    assert 'if self.role_record is not None:' in source
    assert 'if not self.role_record.is_active:' in source
    assert 'return False' in source


def test_user_lifecycle_service_has_permission_defense_in_depth() -> None:
    source = Path('app/users/service.py').read_text(encoding='utf-8')

    for permission in ('users.manage', 'users.activate'):
        assert f"actor.has_permission('{permission}')" in source
