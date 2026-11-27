"""Non-dispatching qualification preflight for provider-origin Vault firing delivery.

Existing routing policies and delivery journals remain authoritative. This
module cannot authorize transport or create a delivery reservation.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError

from app.access.scope_policy import evaluate_exact_vault_instance_operator_scope
from app.extensions.db import db
from app.integrations.delivery.notification_channels.catalog import domain_event_allowed
from app.integrations.delivery.notification_channels.providers import get_notification_provider
from app.intelligence.alert_intelligence.vault_provider_operator import admitted_operator_workflow_qualified
from app.intelligence.alert_intelligence.vault_provider_plan import (
    _provenance_matches,
    admitted_source_state_qualified,
)
from app.intelligence.alert_signals.vault_source import (
    _locked_observation_snapshot,
    _persisted_utc,
    _utc,
    _validated_binding,
    read_vault_alert_observations,
)
from app.models.alert_ops import AlertCase, AlertRoutingPolicy
from app.models.audit import AuditEvent
from app.models.notification_channel import NotificationChannel, NotificationDelivery
from app.models.user import User
from app.security.credentials import CredentialEncryptionError

_SEVERITY_RANK = {'info': 1, 'warning': 2, 'critical': 3}


def _policy_matches_exact_source(
    policy: AlertRoutingPolicy, *, case: AlertCase, binding_id: int, channel_id: int
) -> bool:
    """Candidate policy contract only: one exact source and one destination."""
    return bool(
        policy.enabled
        and policy.domains_json == ['secrets_pki']
        and policy.source_types_json == ['provider_alert']
        and policy.matchers_json == {'vault_instance': case.asset_key, 'source_binding_id': str(binding_id)}
        and isinstance(policy.severities_json, list)
        and policy.severities_json
        and all(isinstance(value, str) and value in _SEVERITY_RANK for value in policy.severities_json)
        and case.severity in policy.severities_json
        and policy.channel_ids_json == [channel_id]
        and not policy.send_resolved
    )


def _channel_matches_candidate(channel: NotificationChannel, *, severity: str, now: datetime) -> bool:
    tested = _persisted_utc(channel.last_tested_at)
    return bool(
        channel.enabled
        and channel.lifecycle_state == 'active'
        and channel.configured
        and channel.test_status == 'success'
        and tested is not None
        and tested <= now
        and channel.domains == ['secrets_pki']
        and channel.event_types == ['alert_ops.firing']
        and severity in _SEVERITY_RANK
        and channel.minimum_severity in _SEVERITY_RANK
        and _SEVERITY_RANK[severity] >= _SEVERITY_RANK[channel.minimum_severity]
        and get_notification_provider(channel.provider_key) is not None
    )


def preflight_vault_provider_firing(
    *,
    binding_id: int,
    instance_id: int,
    public_id: str,
    actor_user_id: int,
    policy_id: int,
    channel_id: int,
    now: datetime | None = None,
) -> str:
    """Return a bounded blocker, never an authorization or a transport payload.

    Candidate review is internal-only. Even a structurally matching policy
    and a tested channel cannot establish approved recipient/target scope.
    """
    instant = _utc(now or datetime.now(UTC))
    if (
        instant is None
        or any(
            type(value) is not int or value < 1
            for value in (binding_id, instance_id, actor_user_id, policy_id, channel_id)
        )
        or not isinstance(public_id, str)
        or not 1 <= len(public_id) <= 64
    ):
        return 'blocked'
    try:
        actor = db.session.get(User, actor_user_id)
        if (
            actor is None
            or not actor.is_active
            or actor.role_record is None
            or not actor.role_record.is_active
            or 'integrations.manage' not in actor.role_record.permission_keys()
        ):
            return 'forbidden'
        eligible = _validated_binding(binding_id, now=instant, lock=True)
        if eligible is None:
            return 'source_unavailable'
        binding, source = eligible
        if binding.asset_key != str(instance_id):
            return 'source_unavailable'
        scope = evaluate_exact_vault_instance_operator_scope(
            actor_user_id=actor_user_id, instance_id=instance_id, now=instant
        )
        if not scope.allowed:
            return 'forbidden'
        snapshot = _locked_observation_snapshot(binding.asset_key)
        if snapshot is None:
            return 'source_unavailable'
        observation = read_vault_alert_observations(binding_id=binding.id, now=instant)
        case = (
            AlertCase.query.filter_by(
                public_id=public_id,
                domain='secrets_pki',
                asset_type='vault_instance',
                asset_key=binding.asset_key,
                source_type='provider_alert',
            )
            .populate_existing()
            .with_for_update(of=AlertCase)
            .first()
        )
        if (
            case is None
            or not _provenance_matches(case, source_id=source.id, binding_id=binding.id)
            or not admitted_source_state_qualified(case)
            or not admitted_operator_workflow_qualified(case)
            or case.source_state != 'firing'
            or _persisted_utc(case.last_seen_at) != _persisted_utc(snapshot.generated_at)
            or observation['state'] != 'fresh'
            or not any(
                entry['handle'] == case.case_key.removeprefix('vault-alert:')
                and entry['source_state'] == 'firing'
                for entry in observation['entries']
            )
        ):
            return 'source_unavailable'
        status = _candidate_blocker(
            case, binding_id=binding.id, policy_id=policy_id, channel_id=channel_id, now=instant
        )
        audit = AuditEvent()
        audit.actor_user_id = actor_user_id
        audit.target_type = 'alert_case'
        audit.target_id = case.public_id
        audit.action = 'vault_provider_delivery_preflight'
        audit.summary = 'Internal scoped delivery qualification reviewed; no transport authorized.'
        audit.metadata_json = {
            'domain': 'secrets_pki',
            'asset_key': case.asset_key,
            'policy_ref': scope.policy_ref,
            'policy_revision': scope.revision,
            'routing_policy_id': policy_id,
            'channel_id': channel_id,
            'result': status,
        }
        db.session.add(audit)
        db.session.commit()
        return status
    except (SQLAlchemyError, CredentialEncryptionError, ValueError, TypeError, AttributeError):
        return 'unavailable'
    finally:
        db.session.rollback()


def _candidate_blocker(
    case: AlertCase, *, binding_id: int, policy_id: int, channel_id: int, now: datetime
) -> str:
    # No repeat/reminder semantics have been admitted for this provider.
    if case.workflow_state != 'open' or case.acknowledged_at is not None:
        return 'workflow_suppressed'
    policy = db.session.get(AlertRoutingPolicy, policy_id, populate_existing=True)
    if policy is None or not _policy_matches_exact_source(
        policy, case=case, binding_id=binding_id, channel_id=channel_id
    ):
        return 'policy_unqualified'
    channel = db.session.get(NotificationChannel, channel_id, populate_existing=True)
    if channel is None or not _channel_matches_candidate(channel, severity=case.severity, now=now):
        return 'channel_unqualified'
    # Journal lookup is independent of policy and repeat bucket. Any existing
    # firing attempt blocks this first-delivery-only qualification slice.
    prior = NotificationDelivery.query.filter(
        NotificationDelivery.channel_id == channel_id,
        NotificationDelivery.event_type == 'alert_ops.firing',
        NotificationDelivery.event_key.startswith(f'alert-case:{case.public_id}:firing:', autoescape=True),
    ).first()
    if prior is not None:
        return 'prior_delivery_review_required'
    if not domain_event_allowed('secrets_pki', 'alert_ops.firing'):
        return 'catalog_unqualified'
    # Catalog membership is not target authorization. There is deliberately
    # no success branch until target governance and retry requalification exist.
    return 'target_authority_unqualified'
