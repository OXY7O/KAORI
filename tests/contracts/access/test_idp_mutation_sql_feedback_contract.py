"""Provider create/edit must preserve form state and expose recoverable SQL failures."""

import ast
from pathlib import Path

ROUTES = Path(__file__).resolve().parents[3] / 'app/access/identity_providers/routes.py'


def test_create_and_edit_have_safe_database_failure_feedback() -> None:
    source = ROUTES.read_text(encoding='utf-8')
    tree = ast.parse(source)
    functions = {
        node.name: ast.get_source_segment(source, node) for node in tree.body if isinstance(node, ast.FunctionDef)
    }

    for route_name, operation, event_type in (
        ('create', 'create_identity_provider', 'identity_provider_create_failed'),
        ('edit', 'update_identity_provider', 'identity_provider_update_failed'),
    ):
        code = functions[route_name]
        assert code is not None
        assert f'{operation}(' in code
        assert 'except IntegrityError:' in code
        assert 'except SQLAlchemyError:' in code
        block = code.split('except SQLAlchemyError:', 1)[1].split('else:', 1)[0]
        assert 'rollback_identity_provider_transaction()' in block
        assert 'current_app.logger.exception(' in block
        assert 'form.key.errors' in block
        assert event_type in block
        assert 'No provider configuration' in block or 'No provider configuration changes' in block
        assert 'str(exc)' not in block
        assert "render_template('access/identity_providers/form.html'" in code


def test_service_already_rolls_back_failed_create_update_commits() -> None:
    service = (Path(__file__).resolve().parents[3] / 'app/access/identity_providers/service.py').read_text(
        encoding='utf-8'
    )
    for method, handler in (
        ('create_identity_provider', 'except SQLAlchemyError:'),
        ('update_identity_provider', 'except (SQLAlchemyError, ProviderIdentityRebindError):'),
    ):
        source = service.split(f'def {method}(', 1)[1]
        source = source.split('\ndef ', 1)[0]
        assert handler in source
        handler_block = source.split(handler, 1)[1].split('\n    return ', 1)[0]
        assert 'db.session.rollback()' in handler_block
        assert '\n        raise' in handler_block
