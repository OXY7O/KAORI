"""Directory provisioning must rollback any database failure at the route boundary."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROUTES = ROOT / 'app/access/identity_providers/routes.py'
PROJECTION = ROOT / 'app/access/identity_providers/provisioning.py'
AUDIT = ROOT / 'app/common/admin_audit.py'


def test_directory_projection_catches_all_sql_transaction_failures() -> None:
    source = ROUTES.read_text(encoding='utf-8')
    tree = ast.parse(source)
    handler = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'provision_identity'
    )
    code = ast.get_source_segment(source, handler)
    assert code is not None
    assert 'provision_external_identity(' in code
    assert 'record_admin_event(' in code
    assert 'commit_identity_projection()' in code
    assert 'except SQLAlchemyError:' in code
    sql_error = code.split('except SQLAlchemyError:', 1)[1].split('else:', 1)[0]
    assert 'rollback_identity_provider_transaction()' in sql_error
    assert "event_type='external_identity_provision_failed'" in sql_error
    assert 'The identity could not be provisioned' in sql_error
    assert 'current_app.logger.exception(' in sql_error


def test_provider_projection_audit_remains_in_caller_transaction() -> None:
    source = PROJECTION.read_text(encoding='utf-8')
    assert source.count('db.session.flush()') >= 2
    audit = AUDIT.read_text(encoding='utf-8')
    assert "Persist one Access administrative audit event in the caller's transaction." in audit
    assert 'db.session.add(event)' in audit
    assert 'db.session.commit()' not in audit
