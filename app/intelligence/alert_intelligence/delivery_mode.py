"""Recommendation delivery mode; provider-origin authority stays independent."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.extensions.db import db
from app.models.alert_ops import AlertCase, AlertDeliveryMode, AlertRoutingPolicy
from app.models.audit import AuditEvent
from app.models.notification_channel import NotificationDelivery

CHANNEL_DEFAULTS = 'channel_defaults'
POLICY_REQUIRED = 'policy_required'
DELIVERY_DISABLED = 'delivery_disabled'
MODES = frozenset({CHANNEL_DEFAULTS, POLICY_REQUIRED, DELIVERY_DISABLED})
DOMAINS = frozenset({'kubernetes', 'object_storage', 'registry'})
EVENTS = frozenset({'alert_ops.firing', 'alert_ops.resolved', 'alert_intelligence.active_alert'})


def routing_mode_view() -> dict[str, Any]:
    # Select columns, not a potentially stale ORM identity-map instance.
    row = db.session.execute(
        select(AlertDeliveryMode.mode, AlertDeliveryMode.revision).where(AlertDeliveryMode.id == 1)
    ).one_or_none()
    if row is None or row.mode not in MODES or row.revision < 1:
        return {'mode': DELIVERY_DISABLED, 'revision': None, 'available': False}
    return {'mode': row.mode, 'revision': row.revision, 'available': True}


def effective_routing_mode() -> str:
    return str(routing_mode_view()['mode'])


def save_routing_mode(*, mode: str, revision: int, actor_user_id: int | None) -> bool:
    if mode not in MODES or revision < 1 or actor_user_id is None:
        raise ValueError('Select a valid routing mode and reload the current revision.')
    row = db.session.get(AlertDeliveryMode, 1, populate_existing=True, with_for_update=True)
    if row is None or row.mode not in MODES or row.revision != revision:
        raise ValueError('Routing configuration changed or is unavailable. Reload before saving.')
    if row.mode == mode:
        db.session.rollback()
        return False
    previous = row.mode
    row.mode = mode
    row.revision += 1
    row.updated_at = datetime.now(UTC)
    audit = AuditEvent()
    audit.actor_user_id = actor_user_id
    audit.target_type = 'alert_intelligence'
    audit.target_id = 'recommendation_delivery_mode'
    audit.action = 'alert_delivery_mode_updated'
    audit.summary = 'Recommendation alert delivery routing mode updated.'
    audit.metadata_json = {'previous_mode': previous, 'mode': mode, 'revision': row.revision}
    db.session.add(audit)
    db.session.commit()
    return True


def _domain_governed(domain: str) -> bool:
    policies = AlertRoutingPolicy.query.filter(AlertRoutingPolicy.domains_json.is_not(None)).all()
    return any(domain in (policy.domains_json or []) for policy in policies)


def recommendation_event_allowed(
    *, domain: str, event_type: str, asset_type: str, asset_key: str,
    event_key: str, channel_id: int, payload: dict[str, Any],
) -> bool:
    """Recheck mode at generic dispatch/replay boundary; never broaden other event families."""
    if domain not in DOMAINS or event_type not in EVENTS:
        return True
    mode = effective_routing_mode()
    if mode == DELIVERY_DISABLED:
        return False
    if event_type == 'alert_intelligence.active_alert':
        return mode == CHANNEL_DEFAULTS and domain != 'registry' and not _domain_governed(domain)
    # In compatibility mode preserve existing per-route delivery semantics.
    # A queued default firing event must not bypass newly governed ownership.
    if mode == CHANNEL_DEFAULTS and domain != 'registry':
        if event_type == 'alert_ops.firing' and payload.get('routing_policy_id') is None:
            return not _domain_governed(domain)
        return True

    # Strict mode and Registry require a current matching policy. Import here
    # to keep the generic delivery module independent of the routing module.
    from app.intelligence.alert_intelligence.routing import firing_routes, policy_allows_resolved

    public_id = payload.get('case_id')
    if not isinstance(public_id, str) or not public_id or not event_key.startswith(f'alert-case:{public_id}:'):
        return False
    case = AlertCase.query.filter_by(public_id=public_id).populate_existing().first()
    if (
        case is None or case.source_type != 'recommendation' or case.domain != domain
        or case.asset_type != asset_type or str(case.asset_key) != str(asset_key)
    ):
        return False
    if event_type == 'alert_ops.firing':
        policy_id = payload.get('routing_policy_id')
        if type(policy_id) is not int or policy_id <= 0 or case.workflow_state == 'closed':
            return False
        if not event_key.startswith(f'alert-case:{public_id}:firing:route-policy-{policy_id}:'):
            return False
        return any(route.policy_id == policy_id and route.channel_id == channel_id for route in firing_routes(case))
    if (
        event_key != f'alert-case:{public_id}:resolved:final'
        or case.source_state != 'resolved' or case.workflow_state != 'closed'
        or not policy_allows_resolved(case, channel_id)
    ):
        return False
    # Resolved cannot be broadcast to a new destination which never received firing.
    return NotificationDelivery.query.filter(
        NotificationDelivery.channel_id == channel_id,
        NotificationDelivery.event_type == 'alert_ops.firing',
        NotificationDelivery.status == 'sent',
        NotificationDelivery.event_key.startswith(f'alert-case:{public_id}:firing:', autoescape=True),
    ).first() is not None
