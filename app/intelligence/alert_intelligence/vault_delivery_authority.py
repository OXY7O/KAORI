"""Independent signed first-firing destination approval (#5253).

A channel test, generic routing policy, or global role is not disclosure
authority. The exact case, binding, policy and channel revisions are pinned
by a separate deployment-managed checker. No transport or credential export.
"""

from __future__ import annotations

from datetime import datetime

from app.access.scope_policy import evaluate_exact_vault_instance_case_scope, lock_explicit_permissions
from app.extensions.db import db
from app.intelligence.alert_signals.vault_authority import read_signed_authority, receipt_time
from app.intelligence.alert_signals.vault_source import _persisted_utc
from app.models.alert_ops import AlertCase, AlertRoutingPolicy
from app.models.integration import IntegrationBinding, IntegrationInstance
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
        'source_id', 'binding_revision', 'source_revision', 'policy_revision', 'channel_revision', 'channel_tested_at', 'event_type',
        'maker_id', 'checker_id', 'issued_at', 'expires_at'
    }:
        return None
    binding = db.session.get(IntegrationBinding, binding_id, populate_existing=True)
    if binding is None or binding.asset_key != case.asset_key:
        return None
    source = db.session.get(IntegrationInstance, binding.integration_instance_id, populate_existing=True)
    if source is None:
        return None
    identifiers = {
        'binding_id': binding_id, 'instance_id': int(case.asset_key), 'policy_id': policy.id,
        'channel_id': channel.id, 'maker_id': actor_id, 'source_id': source.id,
    }
    if any(type(payload[k]) is not int or payload[k] != v for k, v in identifiers.items()):
        return None
    checker = payload['checker_id']
    revisions = (
        _persisted_utc(binding.updated_at), _persisted_utc(source.updated_at),
        _persisted_utc(policy.updated_at), _persisted_utc(channel.updated_at),
        _persisted_utc(channel.last_tested_at),
    )
    if any(value is None for value in revisions):
        return None
    if (
        payload['case_id'] != case.public_id
        or payload['event_type'] != 'alert_ops.firing'
        or type(checker) is not int or checker <= 0 or checker == actor_id
        or receipt_time(payload['binding_revision']) != _persisted_utc(binding.updated_at)
        or receipt_time(payload['source_revision']) != _persisted_utc(source.updated_at)
        or receipt_time(payload['policy_revision']) != _persisted_utc(policy.updated_at)
        or receipt_time(payload['channel_revision']) != _persisted_utc(channel.updated_at)
        or receipt_time(payload['channel_tested_at']) != _persisted_utc(channel.last_tested_at)
        or not lock_explicit_permissions(checker, _CHECKER_PERMISSIONS)
    ):
        return None
    if not evaluate_exact_vault_instance_case_scope(
        actor_user_id=checker, instance_id=int(case.asset_key), now=now
    ).allowed:
        return None
    return evidence_ref
