"""Default-disabled authenticated web adapter for scoped Vault operator commands."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from flask import abort, make_response, redirect, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from sqlalchemy.exc import SQLAlchemyError
from wtforms.validators import ValidationError

from app.access.scope_policy import evaluate_exact_vault_instance_operator_scope
from app.extensions.db import db
from app.intelligence.alert_intelligence.vault_provider_admission import _ENABLE_ENV
from app.intelligence.alert_intelligence.vault_provider_operator import (
    _latest_event_id,
    admitted_operator_workflow_qualified,
    apply_vault_provider_operator_action,
)
from app.intelligence.alert_intelligence.vault_provider_plan import (
    _provenance_matches,
    admitted_source_state_qualified,
)
from app.intelligence.alert_signals.vault_source import (
    _locked_observation_snapshot,
    _persisted_utc,
    _validated_binding,
    read_vault_alert_observations,
)
from app.models.alert_ops import AlertCase
from app.models.integration import IntegrationBinding
from app.models.scope_access import ScopeAccessPolicy
from app.models.user import User
from app.platform_operations.notifications.service import create_transient_feedback, stage_operational_activity

_WEB_ENABLE_ENV = 'KAORI_VAULT_PROVIDER_CASE_OPERATOR_WEB_ENABLED'
_MAX_RECIPIENTS = 32


def _enabled() -> bool:
    return os.getenv(_ENABLE_ENV) == 'true' and os.getenv(_WEB_ENABLE_ENV) == 'true'


def _positive(raw: str | None) -> int | None:
    if not raw or not raw.isascii() or not raw.isdecimal() or len(raw) > 18 or raw.startswith('0'):
        return None
    return int(raw)


def _binding_id(instance_id: int) -> int | None:
    rows = (
        db.session.query(IntegrationBinding.id)
        .filter_by(asset_type='vault_instance', asset_key=str(instance_id), enabled=True)
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


def operator_controls(*, instance_id: int, public_id: str, expected_event_id: int) -> dict[str, Any] | None:
    """Independent audited read of eligible actions after the case read commits.

    Binding-first order matches the mutation command. No fleet/user enumeration;
    selector candidates originate only from the exact decision scope.
    """
    if not _enabled():
        return None
    actor_id = getattr(current_user, 'id', None)
    if type(actor_id) is not int:
        return None
    now = datetime.now(UTC)
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
        if (
            case is None
            or not _provenance_matches(case, source_id=source.id, binding_id=binding.id)
            or not admitted_source_state_qualified(case)
            or not admitted_operator_workflow_qualified(case)
            or case.source_state != 'firing'
            or _persisted_utc(case.last_seen_at) != _persisted_utc(snapshot.generated_at)
            or observation['state'] != 'fresh'
            or not any(
                entry['handle'] == case.case_key.removeprefix('vault-alert:') and entry['source_state'] == 'firing'
                for entry in observation['entries']
            )
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


def operator_action_response(public_id: str) -> ResponseReturnValue:
    """Accept only explicit scoped form input; actor is the authenticated session."""
    if not _enabled():
        abort(404)
    try:
        validate_csrf(request.form.get('csrf_token'))
    except ValidationError:
        abort(400)
    actor_id = getattr(current_user, 'id', None)
    instance_id = _positive(request.form.get('instance_id'))
    expected = _positive(request.form.get('expected_event_id'))
    action = request.form.get('action', '')
    if type(actor_id) is not int or instance_id is None or expected is None:
        abort(404)
    fields = {'csrf_token', 'instance_id', 'expected_event_id', 'action'}
    if action == 'assign':
        fields.add('owner_user_id')
    if action not in {'acknowledge', 'assign', 'mitigating'} or set(request.form) != fields:
        abort(400)
    if any(len(request.form.getlist(key)) != 1 for key in fields):
        abort(400)
    owner = None
    if action == 'assign':
        raw_owner = request.form.get('owner_user_id')
        if raw_owner != '':
            owner = _positive(raw_owner)
            if owner is None:
                abort(400)
    try:
        binding_id = _binding_id(instance_id)
    except SQLAlchemyError:
        db.session.rollback()
        abort(404)
    db.session.rollback()
    if binding_id is None:
        abort(404)
    status = apply_vault_provider_operator_action(
        binding_id=binding_id,
        instance_id=instance_id,
        public_id=public_id,
        actor_user_id=actor_id,
        action=action,
        expected_event_id=expected,
        owner_user_id=owner,
    )
    if status not in {'committed', 'unchanged', 'stale'}:
        abort(404)
    create_transient_feedback(
        status='success' if status == 'committed' else 'warning',
        title='Alert workflow updated' if status == 'committed' else 'Alert workflow not changed',
        message=(
            'The operator workflow and audit evidence were committed.'
            if status == 'committed'
            else 'Refresh the committed case before repeating an action.'
        ),
        queue_feedback=True,
    )
    destination = url_for(
        'alert_intelligence.case_details',
        public_id=public_id,
        domain='secrets_pki',
        provider='vault',
        asset=instance_id,
        tab='active',
    )
    if request.headers.get('HX-Request') == 'true':
        response = make_response('', 200)
        response.headers['HX-Redirect'] = destination
        return response
    return redirect(destination, code=303)
