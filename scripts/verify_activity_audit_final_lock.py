#!/usr/bin/env python3
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
    routes = read('app/access/activity_audit/routes.py')
    service = read('app/access/activity_audit/service.py')
    notification_routes = read('app/notifications/routes.py')
    queries = read('app/notifications/queries.py')
    model = read('app/models/notification.py')
    actors = read('app/notifications/actors.py')
    writer = read('app/notifications/writer.py')
    auth_audit = read('app/auth/audit.py')
    event_catalog = read('app/notifications/event_catalog.py')
    page = read('app/templates/access/activity_audit/index.html')
    summary = read('app/templates/access/activity_audit/partials/_activity_summary_cards.html')
    table = read('app/templates/access/activity_audit/partials/_activity_table_card.html')
    migration = read('migrations/versions/20260817_activity_audit_evidence_foundation.py')
    retention = read('app/retention/domains/operational_activity.py')

    for required in (
        "@permission_required('activity_audit.view')",
        "@bp.get('/')",
        "@bp.get('/<int:notification_id>/details')",
        "render_template('access/activity_audit/index.html'",
    ):
        require(required in routes, f'Activity Audit route contract missing: {required}', errors)
    require(
        "@notifications_bp.get('/activity')" not in notification_routes,
        'Notification Center still owns Activity Audit route',
        errors,
    )
    for legacy in (
        'app/templates/notifications/activity.html',
        'app/templates/notifications/partials/_activity_detail.html',
        'app/templates/notifications/partials/_activity_summary_cards.html',
        'app/templates/notifications/partials/_activity_table_card.html',
        'app/templates/notifications/partials/_activity_table_content.html',
    ):
        require(not (ROOT / legacy).exists(), f'Legacy Activity Audit template remains: {legacy}', errors)

    for required in (
        "db.ForeignKey('users.id', ondelete='SET NULL')",
        'category_key: Mapped[str]',
        'actor_key: Mapped[str]',
        'actor_label: Mapped[str]',
        'actor_snapshot_json: Mapped[dict[str, Any]]',
    ):
        require(required in model, f'Activity Audit model contract missing: {required}', errors)
    for required in (
        "key='system:kaori'",
        "key='unauthenticated'",
        'def resolve_operational_actor(',
        'actor_snapshot_for_user(',
    ):
        require(required in actors, f'Actor snapshot contract missing: {required}', errors)
    for required in (
        'notification.category_key = event_category_key(event_type)',
        'notification.actor_key = evidence.actor.key',
        'notification.actor_label = evidence.actor.label',
        'notification.actor_snapshot_json = evidence.actor.as_json()',
    ):
        require(required in writer, f'Activity writer contract missing: {required}', errors)
    require('activity.deck_visible = False' in auth_audit, 'Authentication audit must remain audit-only', errors)

    for required in (
        'Notification.actor_key == normalized_actor_key',
        'Notification.category_key == normalized_category',
        'Notification.actor_label.ilike(pattern)',
        'func.count(func.distinct(Notification.actor_key))',
        "('all', 'All Hot Records')",
    ):
        require(required in queries, f'Activity query contract missing: {required}', errors)
    require(
        '_activity_category_condition' not in queries, 'Activity query still duplicates category routing logic', errors
    )
    require(
        'def activity_category_keys()' in event_catalog,
        'Activity category order must come from source-controlled catalog',
        errors,
    )
    require(
        'get_notification_activity_context' in service,
        'Access Activity service must consume shared evidence query kernel',
        errors,
    )

    require(
        'Evidence Availability' in page,
        'Activity hero must describe evidence availability, not event severity as health',
        errors,
    )
    require(
        'Actor Evidence' in summary and 'Immutable' in summary,
        'Activity summary must expose immutable actor boundary',
        errors,
    )
    require(
        'This register reads hot PostgreSQL records.' in summary,
        'Activity summary must expose hot/archive boundary',
        errors,
    )
    require(
        "filters.time_range != '7d'" in table,
        'Clear Filters must reset Activity Audit to canonical 7-day range',
        errors,
    )
    require("time_range='7d'" in table, 'Clear Filters must preserve canonical 7-day range', errors)

    for required in (
        'schema_version = 2',
        "'recipient_user_id': notification.user_id",
        "'actor_snapshot': dict(notification.actor_snapshot_json or {})",
    ):
        require(required in retention, f'Activity archive evidence contract missing: {required}', errors)
    require(
        'outerjoin(User' not in retention,
        'Activity archive must not reconstruct actor identity from live users',
        errors,
    )
    require(
        'from app.models.user import User' not in retention,
        'Activity archive must not depend on live User records',
        errors,
    )

    for required in (
        "revision = '20260817_activity_audit_v1'",
        "down_revision = '20260817_permission_contract_v1'",
        "ondelete='SET NULL'",
        "'actor_snapshot_json'",
        "'category_key'",
    ):
        require(required in migration, f'Activity Audit migration contract missing: {required}', errors)

    if errors:
        for error in errors:
            print(f'ERROR: {error}')
        return 1
    print('PASS — KAORI Activity Audit Final Lock v1')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
