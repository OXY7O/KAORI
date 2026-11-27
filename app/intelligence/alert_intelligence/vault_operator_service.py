"""Application service for scoped Vault operator control qualification."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.access.scope_policy import evaluate_exact_vault_instance_operator_scope
from app.extensions.db import db
from app.intelligence.alert_intelligence.vault_provider_admission import _ENABLE_ENV
from app.intelligence.alert_intelligence.vault_provider_operator import _current_firing_case, _latest_event_id
from app.intelligence.alert_signals.vault_source import (
    _locked_observation_snapshot,
    _utc,
    _validated_binding,
    read_vault_alert_observations,
)
from app.models.alert_ops import AlertCase
from app.models.integration import IntegrationBinding, IntegrationInstance
from app.models.scope_access import ScopeAccessPolicy
from app.models.user import User
from app.platform_operations.notifications.service import stage_operational_activity

_MAX_RECIPIENTS = 32


def _binding_id(instance_id: int) -> int | None:
    rows = (
        db.session.query(IntegrationBinding.id)
        .join(IntegrationInstance, IntegrationInstance.id == IntegrationBinding.integration_instance_id)
        .filter(
            IntegrationBinding.asset_type == 'vault_instance',
            IntegrationBinding.asset_key == str(instance_id),
            IntegrationBinding.enabled.is_(True),
            IntegrationInstance.integration_type == 'alert_source',
            IntegrationInstance.enabled.is_(True),
            IntegrationInstance.lifecycle_status == 'active',
        )
        .limit(2)
        .all()
    )
    return rows[0][0] if len(rows) == 1 else None


def _recipient_options(instance_id: int, *, now: datetime) -> list[dict[str, Any]] | None:
    ids = (
        db.session.query(ScopeAccessPolicy.principal_user_id)
        .filter_by(
            permission_key='intelligence.decisions.create',
            integration_instance_id=instance_id,
            scope_level='instance',
            provider_namespace=None,
            mount=None,
        )
        .distinct()
        .order_by(ScopeAccessPolicy.principal_user_id)
        .limit(_MAX_RECIPIENTS + 1)
        .all()
    )
    if len(ids) > _MAX_RECIPIENTS:
        return None
    options = []
    for (user_id,) in ids:
        scope = evaluate_exact_vault_instance_operator_scope(actor_user_id=user_id, instance_id=instance_id, now=now)
        if scope.status == 'unavailable':
            return None
        if scope.allowed:
            user = db.session.get(User, user_id)
            if user is not None:
                options.append({'id': user.id, 'label': user.username})
    return options


def load_operator_controls(
    *, instance_id: int, public_id: str, expected_event_id: int, actor_id: int, now: datetime | None = None
) -> dict[str, Any] | None:
    """Independent audited read of eligible actions after the case read commits.

    Binding-first order matches the mutation command. No fleet/user enumeration;
    selector candidates originate only from the exact decision scope.
    """
    if os.getenv(_ENABLE_ENV) != 'true':
        return None
    now = _utc(now or datetime.now(UTC))
    if now is None:
        return None
    try:
        binding_id = _binding_id(instance_id)
        eligible = _validated_binding(binding_id, now=now, lock=True) if binding_id is not None else None
        if eligible is None:
            return None
        binding, source = eligible
        if binding.asset_key != str(instance_id):
            return None
        scope = evaluate_exact_vault_instance_operator_scope(actor_user_id=actor_id, instance_id=instance_id, now=now)
        if not scope.allowed:
            return None
        # Recipient locks precede snapshot/case locks, as in the command.
        options = _recipient_options(instance_id, now=now)
        if options is None:
            return None
        snapshot = _locked_observation_snapshot(binding.asset_key)
        if snapshot is None:
            return None
        observation = read_vault_alert_observations(binding_id=binding.id, now=now)
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
        if case is None or observation['state'] != 'fresh':
            return None
        if not _current_firing_case(
            case,
            source_id=source.id,
            binding_id=binding.id,
            generated_at=snapshot.generated_at,
            entries=observation['entries'],
        ):
            return None
        event_id = _latest_event_id(case)
        if event_id is None or event_id != expected_event_id:
            return None
        result = {
            'expected_event_id': event_id,
            'acknowledge': case.workflow_state == 'open',
            'mitigating': case.workflow_state == 'acknowledged' and case.owner_user_id == actor_id,
            'recipients': options,
            'owner_user_id': case.owner_user_id if any(item['id'] == case.owner_user_id for item in options) else None,
            'has_owner': case.owner_user_id is not None,
        }
        stage_operational_activity(
            user_id=actor_id,
            event_type='vault_provider_case_operator_controls_read',
            status='info',
            title='Vault Operator Controls Read',
            message='Qualified exact-instance operator controls were accessed.',
            metadata={
                'integration_instance_id': instance_id,
                'permission_key': 'intelligence.decisions.create',
                'policy_ref': scope.policy_ref,
                'policy_revision': scope.revision,
            },
        )
        db.session.commit()
        return result
    except (SQLAlchemyError, ValueError, TypeError, AttributeError):
        return None
    finally:
        db.session.rollback()


def resolve_operator_binding(instance_id: int) -> int | None:
    """Resolve the exact active alert source; the command requalifies under lock."""
    try:
        return _binding_id(instance_id)
    except SQLAlchemyError:
        return None
    finally:
        db.session.rollback()
