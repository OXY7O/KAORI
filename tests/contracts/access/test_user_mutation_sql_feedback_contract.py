"""User create/edit non-unique SQL failures surface safe and recoverable errors."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_create_edit_handlers_handle_all_sql_errors_without_leaking_details() -> None:
    source = (ROOT / 'app/access/users/routes.py').read_text(encoding='utf-8')
    for name, ending, expected in (
        ('create()', 'edit(user_id: int)', 'The user could not be created due to a database error. Please retry.'),
        ('edit(user_id: int)', 'activate(user_id: int)', 'The user changes could not be saved due to a database error. Please retry.'),
    ):
        section = source.split(f'def {name}:', 1)[1].split(f'def {ending}:', 1)[0]
        assert 'except IntegrityError:' in section
        assert 'except SQLAlchemyError:' in section
        assert expected in section
        assert 'form.username.errors' in section
        assert 'current_app.logger.exception(' in section
        assert "render_template(\n        'access/users/form.html'" in section


def test_create_edit_service_rollback_and_audit_remain_authoritative() -> None:
    service = (ROOT / 'app/access/users/service.py').read_text(encoding='utf-8')
    for name in ('persist_created_user', 'persist_updated_user'):
        section = service.split(f'def {name}(', 1)[1].split('\ndef ', 1)[0]
        assert 'record_admin_event(' in section
        assert 'db.session.commit()' in section
        assert 'except SQLAlchemyError:' in section
        assert 'db.session.rollback()' in section
