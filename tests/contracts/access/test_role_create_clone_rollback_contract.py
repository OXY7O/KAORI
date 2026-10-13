"""Roles create and clone must retain the canonical rollback/error contract."""

import ast
from pathlib import Path

ROUTES = Path(__file__).resolve().parents[3] / 'app/access/roles/routes.py'


def test_role_create_clone_database_failure_routes_are_bounded() -> None:
    tree = ast.parse(ROUTES.read_text(encoding='utf-8'))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

    for name, event in (
        ('create', 'rbac_role_create_failed'),
        ('clone', 'rbac_role_clone_failed'),
    ):
        code = ast.get_source_segment(ROUTES.read_text(encoding='utf-8'), functions[name])
        assert code is not None
        assert 'except (SQLAlchemyError, ValueError):' in code
        assert 'rollback_role_transaction()' in code
        assert 'form.name.errors' in code
        assert event in code
        assert 'No role changes were saved.' in code
        assert code.index(
            'rollback_role_transaction()', code.index('except (SQLAlchemyError, ValueError):')
        ) < code.index('role_access_feedback(', code.index('except (SQLAlchemyError, ValueError):'))
        assert 'form.validate_on_submit()' in code

    assert 'lock_role_for_mutation(role_id)' in ROUTES.read_text(encoding='utf-8')
