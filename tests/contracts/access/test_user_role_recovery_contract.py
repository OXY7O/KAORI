"""User role-recovery may open management forms, but still enforces POST delegation."""

from pathlib import Path

from app.access.users import service


def test_role_recovery_has_separate_get_and_post_guards() -> None:
    routes = (Path(__file__).resolve().parents[3] /
              'app/access/users/routes.py').read_text(encoding='utf-8')
    source = (Path(__file__).resolve().parents[3] /
              'app/access/users/service.py').read_text(encoding='utf-8')
    assert 'validate_new_role: bool = True' in source
    assert 'if validate_new_role:' in source
    assert source.count('validate_new_role=False,') == 1
    assert routes.count('validate_new_role=False,') == 1
    assert 'requested_role_assignment_allowed(actor, requested_role_id)' in source


def test_management_guard_allows_inactive_role_recovery_without_granting_role(monkeypatch) -> None:
    class Actor:
        id = 10
        is_super_admin = False

        def has_permission(self, key):
            return key == 'users.manage'

    class Target:
        id = 11
        deleted_at = None
        auth_source = 'database'
        is_super_admin = False
        account_is_active = True
        role_id = 4
        role_record = None

    actor, target = Actor(), Target()
    monkeypatch.setattr(service, 'is_admin_level_user', lambda user: False)
    monkeypatch.setattr(service, 'requested_admin_level', lambda **kwargs: False)
    monkeypatch.setattr(
        service, 'requested_role_assignment_allowed',
        lambda actor, role_id: (False, 'The selected role is unavailable.'),
    )
    assert service.can_edit_user(
        actor, target, requested_role_id=4,
        requested_is_active=True, requested_is_super_admin=False,
        validate_new_role=False,
    )[0] is True
    assert service.can_edit_user(
        actor, target, requested_role_id=4,
        requested_is_active=True, requested_is_super_admin=False,
    ) == (False, 'The selected role is unavailable.')
