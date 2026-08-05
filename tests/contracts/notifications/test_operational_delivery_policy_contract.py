from __future__ import annotations

import ast
from enum import StrEnum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def _load_delivery_policy_class():
    source = read('app/notifications/feedback.py')
    tree = ast.parse(source)
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == 'OperationalDeliveryPolicy'
    )
    module = ast.Module(body=[class_node], type_ignores=[])
    namespace = {'StrEnum': StrEnum}
    exec(compile(module, 'feedback-policy', 'exec'), namespace)
    return namespace['OperationalDeliveryPolicy']


def test_delivery_policy_semantics_are_executable() -> None:
    policy = _load_delivery_policy_class()

    assert policy.AUDIT_ONLY.deck_visible('success') is False
    assert policy.AUDIT_ONLY.deck_visible('error') is False
    assert policy.DECK_ON_FAILURE.deck_visible('success') is False
    assert policy.DECK_ON_FAILURE.deck_visible('warning') is True
    assert policy.DECK_ON_FAILURE.deck_visible('error') is True
    assert policy.PERSISTENT.deck_visible('success') is True


def test_notification_deck_reads_only_visible_rows() -> None:
    model = read('app/models/notification.py')
    queries = read('app/notifications/queries.py')
    migration = read('migrations/versions/20260805_notification_deck_v2.py')

    assert 'deck_visible: Mapped[bool]' in model
    assert "Index('ix_notifications_user_deck_created', 'user_id', 'deck_visible', 'created_at')" in model
    assert 'Notification.deck_visible.is_(True)' in queries
    assert "revision = '20260805_notification_deck_v2'" in migration
    assert "down_revision = '20260805_secret_ops_v2'" in migration


def test_configmap_secret_and_tls_delivery_matrix_is_explicit() -> None:
    configmap_routes = read('app/kubernetes_operations/configmaps/routes.py')
    secret_support = read('app/kubernetes_operations/secrets/route_support.py')
    tls_routes = read('app/governance/tls_certificates/routes.py')
    tls_tasks = read('app/governance/tls_certificates/tasks.py')

    assert 'OperationalDeliveryPolicy.DECK_ON_FAILURE' in configmap_routes
    assert "event_type == 'kubernetes_configmap_deleted'" in configmap_routes
    assert 'create_transient_feedback(' in configmap_routes

    assert "'_deleted'" in secret_support
    assert "'_rotation'" in secret_support
    assert "event_type == 'kubernetes_secret_revealed'" in secret_support
    assert 'OperationalDeliveryPolicy.AUDIT_ONLY' in secret_support
    assert 'OperationalDeliveryPolicy.DECK_ON_FAILURE' in secret_support

    assert 'queue_transient_feedback(' in tls_routes
    assert 'OperationalDeliveryPolicy.PERSISTENT' in tls_routes
    assert 'notification_deck_user_ids' in tls_tasks
    assert tls_tasks.index('deck_user_ids = _notify_requesters(') < tls_tasks.index('context.succeed(')


def test_tls_uses_canonical_workspace_and_progress_toast() -> None:
    workspace = read('app/templates/governance/tls_certificates/partials/_page_workspace.html')
    progress = read('app/templates/governance/tls_certificates/partials/_sync_progress_toast.html')

    assert 'id="tls-certificates-page-workspace"' in workspace
    assert '_sync_progress_toast.html' in workspace
    assert 'components/operational_progress_toast.html' in progress
    assert not (ROOT / 'app/governance/tls_certificates/toast.py').exists()
    assert not (ROOT / 'app/templates/governance/tls_certificates/partials/_inventory_scope.html').exists()
