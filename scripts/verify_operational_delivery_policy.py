from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    feedback = read('app/platform_operations/notifications/feedback.py')
    service = read('app/platform_operations/notifications/service.py')
    writer = read('app/platform_operations/notifications/writer.py')
    queries = read('app/platform_operations/notifications/queries.py')
    model = read('app/models/notification.py')
    migration = read('migrations/versions/20260805_notification_deck_v2.py')
    toast = read('app/templates/components/operational_toast.html')
    configmap_routes = read('app/kubernetes/operations/configmaps/routes.py')
    secret_feedback = read('app/kubernetes/operations/secrets/route_support.py')
    tls_routes = read('app/kubernetes/governance/tls_certificates/routes.py')
    tls_tasks = read('app/kubernetes/governance/tls_certificates/tasks.py')
    tls_presentation = read('app/kubernetes/governance/tls_certificates/job_presentation.py')
    tls_workspace = read('app/templates/kubernetes/governance/tls_certificates/partials/_page_workspace.html')
    quality_gate = read('scripts/quality_gate.sh')

    for token in (
        'class OperationalDeliveryPolicy(StrEnum)',
        "AUDIT_ONLY = 'audit_only'",
        "DECK_ON_FAILURE = 'deck_on_failure'",
        "PERSISTENT = 'persistent'",
        'def deck_visible(self, status: str) -> bool',
    ):
        require(token in feedback, f'Operational delivery policy missing token: {token}', errors)

    for token in (
        'delivery_policy: OperationalDeliveryPolicy | str',
        'deck_visible = policy.deck_visible(normalized_status)',
        'notification_deck_visible=deck_visible and activity_audit_saved',
        'def create_transient_feedback(',
        'activity_audit_expected=False',
    ):
        require(token in service or token in feedback, f'Notification orchestration missing token: {token}', errors)

    require(
        'deck_visible: Mapped[bool]' in model, 'Notification model must persist Notification Deck visibility.', errors
    )
    require(
        "Index('ix_notifications_user_deck_created', 'user_id', 'deck_visible', 'created_at')" in model,
        'Notification model must declare the Deck visibility query index.',
        errors,
    )
    require(
        "revision = '20260805_notification_deck_v2'" in migration,
        'Notification Deck migration must remain registered.',
        errors,
    )
    require(
        "down_revision = '20260805_secret_ops_v2'" in migration,
        'Notification Deck migration must follow Secret operations v2.',
        errors,
    )
    require(
        "'deck_visible'" in migration and 'ix_notifications_user_deck_created' in migration,
        'Notification Deck migration must add the visibility field and index.',
        errors,
    )
    require(
        'notification.deck_visible = bool(deck_visible)' in writer,
        'Notification persistence must write Deck visibility explicitly.',
        errors,
    )
    require(
        'Notification.deck_visible.is_(True)' in queries,
        'Notification Deck query must exclude audit-only rows.',
        errors,
    )

    for token in ('Activity Audit', 'Notification Deck', 'resolved_notification_deck_visible'):
        require(token in toast, f'Operational toast missing delivery evidence: {token}', errors)

    require(
        'OperationalDeliveryPolicy.DECK_ON_FAILURE' in configmap_routes,
        'ConfigMap create/update outcomes must use Deck-on-failure delivery.',
        errors,
    )
    require(
        "event_type == 'kubernetes_configmap_deleted'" in configmap_routes
        and 'OperationalDeliveryPolicy.PERSISTENT' in configmap_routes,
        'ConfigMap delete must use persistent delivery.',
        errors,
    )
    require('create_transient_feedback(' in configmap_routes, 'ConfigMap validation must remain transient.', errors)

    require(
        "'_deleted'" in secret_feedback and "'_rotation'" in secret_feedback,
        'Secret delete and TLS rotation must use persistent event classification.',
        errors,
    )
    require(
        "event_type == 'kubernetes_secret_revealed'" in secret_feedback
        and 'OperationalDeliveryPolicy.AUDIT_ONLY' in secret_feedback,
        'One-time Secret reveal completion must be audit-only.',
        errors,
    )
    require(
        'OperationalDeliveryPolicy.DECK_ON_FAILURE' in secret_feedback,
        'Secret create/replace outcomes must use Deck-on-failure delivery.',
        errors,
    )
    require(
        'create_transient_feedback(' in secret_feedback,
        'Secret and TLS validation feedback must remain transient.',
        errors,
    )

    require(
        'queue_transient_feedback(' in tls_routes,
        'Accepted TLS sync dispatch must use transient queued feedback.',
        errors,
    )
    require(
        'delivery_policy=OperationalDeliveryPolicy.PERSISTENT' in tls_routes,
        'TLS sync dispatch blockers must use persistent delivery.',
        errors,
    )
    require(
        '_sync_progress_toast.html' in tls_workspace, 'TLS workspace must use the canonical progress toast.', errors
    )
    require(
        'notification_deck_user_ids' in tls_tasks and 'activity_audit_saved' in tls_tasks,
        'TLS worker terminal result must persist delivery evidence.',
        errors,
    )
    require(
        tls_tasks.index('deck_user_ids = _notify_requesters(') < tls_tasks.index('context.succeed('),
        'TLS worker must persist terminal Deck evidence before closing a successful job.',
        errors,
    )
    require(
        'notification_deck_visible = user_id is not None and' in tls_presentation,
        'TLS terminal presentation must report requester-specific Deck persistence.',
        errors,
    )

    obsolete = (
        'app/kubernetes/governance/tls_certificates/toast.py',
        'app/templates/kubernetes/governance/tls_certificates/partials/_inventory_scope.html',
        'app/templates/kubernetes/governance/tls_certificates/partials/_content.html',
        'app/templates/kubernetes/governance/tls_certificates/partials/_sync_toast.html',
    )
    for relative in obsolete:
        require(not (ROOT / relative).exists(), f'Legacy TLS file must remain removed: {relative}', errors)

    require(
        'verify_operational_delivery_policy.py' in quality_gate,
        'Operational delivery policy verifier must run in quality gate.',
        errors,
    )

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1

    print(
        'KAORI operational delivery policy passed: Activity Audit persistence, Notification Deck '
        'visibility, ConfigMap/Secret foreground outcomes, TLS progress, and terminal delivery are aligned.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
