"""Independent signed first-firing destination approval (#5253).

A channel test, generic routing policy, or global role is not disclosure
authority. The exact case, binding, policy and channel revisions are pinned
by a separate deployment-managed checker. No transport or credential export.
"""

from __future__ import annotations

from datetime import datetime

from app.access.scope_policy import lock_explicit_permissions
from app.intelligence.alert_signals.vault_authority import read_signed_authority, receipt_time
from app.intelligence.alert_signals.vault_source import _persisted_utc
from app.models.alert_ops import AlertCase, AlertRoutingPolicy
from app.models.notification_channel import NotificationChannel

_SCHEMA = 'kaori.vault.alert_destination.v1'
_CHECKER_PERMISSIONS = {'roles.manage', 'users.manage', 'integrations.manage'}


def qualify_destination_receipt(
    case: AlertCase, *, binding_id: int, policy: AlertRoutingPolicy, channel: NotificationChannel,
    actor_id: int, now: datetime
) -> str | None:
    """Return an opaque receipt reference, never a transport permit.

    Exact revision uses updated_at deliberately: any channel or policy update
    (including delivery bookkeeping) invalidates this one-attempt receipt.
    """
    signed = read_signed_authority(f'delivery-{binding_id}-{policy.id}-{channel.id}', schema=_SCHEMA, now=now)
    if signed is None:
        return None
    payload, evidence_ref = signed
    if set(payload) != {
        'schema', 'state', 'binding_id', 'instance_id', 'case_id', 'policy_id', 'channel_id',
        'policy_revision', 'channel_revision', 'channel_tested_at', 'event_type',
        'maker_id', 'checker_id', 'issued_at', 'expires_at'
    }:
        return None
    identifiers = {
        'binding_id': binding_id, 'instance_id': int(case.asset_key), 'policy_id': policy.id,
        'channel_id': channel.id, 'maker_id': actor_id,
    }
    if any(type(payload[k]) is not int or payload[k] != v for k, v in identifiers.items()):
        return None
    checker = payload['checker_id']
    if (
        payload['case_id'] != case.public_id
        or payload['event_type'] != 'alert_ops.firing'
        or type(checker) is not int or checker <= 0 or checker == actor_id
        or receipt_time(payload['policy_revision']) != _persisted_utc(policy.updated_at)
        or receipt_time(payload['channel_revision']) != _persisted_utc(channel.updated_at)
        or receipt_time(payload['channel_tested_at']) != _persisted_utc(channel.last_tested_at)
        or not lock_explicit_permissions(checker, _CHECKER_PERMISSIONS)
    ):
        return None
    return evidence_ref
