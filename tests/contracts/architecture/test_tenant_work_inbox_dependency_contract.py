"""Source contract for app-scoped Tenant Work Inbox composition."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_notification_read_model_does_not_import_tenant_domain() -> None:
    source = (ROOT / 'app/platform_operations/notifications/queries.py').read_text(encoding='utf-8')
    module = ast.parse(source)
    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.startswith('app.kubernetes.tenant')
        for node in ast.walk(module)
    )
    assert "current_app.extensions.get('kaori_tenant_approval_work_inbox')" in source
    assert "raise RuntimeError('Tenant approval Work Inbox provider is not registered.')" in source
    assert "tenant_approval_inbox = tenant_inbox_provider(user_id=user_id)" in source


def test_bootstrap_registers_tenant_owned_provider_per_application() -> None:
    source = (ROOT / 'app/bootstrap/blueprints.py').read_text(encoding='utf-8')
    assert 'from app.kubernetes.tenant.approval_inbox import get_tenant_release_work_inbox' in source
    assert "app.extensions['kaori_tenant_approval_work_inbox'] = get_tenant_release_work_inbox" in source
    assert 'app.register_blueprint(blueprint)' in source
