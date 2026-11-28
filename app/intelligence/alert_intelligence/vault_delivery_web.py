"""Thin authenticated local Vault destination policy and firing adapter."""

from __future__ import annotations

from flask import abort, make_response, redirect, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

from app.intelligence.alert_intelligence.vault_delivery_command import (
    DeliveryIntent,
    create_local_vault_policy,
    disable_local_vault_policy,
    execute_local_vault_delivery,
)
from app.intelligence.alert_intelligence.vault_operator_service import resolve_operator_binding
from app.intelligence.alert_intelligence.vault_provider_admission import local_reconcile_enabled
from app.intelligence.alert_intelligence.vault_provider_delivery import preflight_vault_provider_firing
from app.platform_operations.notifications.service import create_transient_feedback


def _positive(key: str) -> int:
    value = request.form.get(key, '')
    if not value.isascii() or not value.isdecimal() or value.startswith('0') or len(value) > 10:
        abort(400)
    number = int(value)
    if not 0 < number <= 2_147_483_647:
        abort(400)
    return number


def _validate(fields: set[str]) -> tuple[int, int, int]:
    if not local_reconcile_enabled():
        abort(404)
    try:
        validate_csrf(request.form.get('csrf_token'))
    except ValidationError:
        abort(400)
    if set(request.form) != fields or any(len(request.form.getlist(key)) != 1 for key in fields):
        abort(400)
    actor = getattr(current_user, 'id', None)
    instance = _positive('instance_id')
    binding = resolve_operator_binding(instance)
    if type(actor) is not int or binding is None:
        abort(404)
    return actor, instance, binding


def _redirect(destination: str) -> ResponseReturnValue:
    if request.headers.get('HX-Request') == 'true':
        response = make_response('', 200)
        response.headers['HX-Redirect'] = destination
        return response
    return redirect(destination, code=303)


def local_policy_response() -> ResponseReturnValue:
    if 'policy_id' in request.form:
        actor, instance, binding = _validate({'csrf_token', 'instance_id', 'policy_id'})
        changed = disable_local_vault_policy(
            instance_id=instance, binding_id=binding, actor_id=actor, policy_id=_positive('policy_id')
        )
        message = 'Candidate disabled; existing approval is no longer usable.' if changed else 'Candidate not changed.'
    else:
        actor, instance, binding = _validate({'csrf_token', 'instance_id', 'channel_id'})
        policy = create_local_vault_policy(
            instance_id=instance, binding_id=binding, actor_id=actor, channel_id=_positive('channel_id')
        )
        changed = policy is not None
        message = (
            f'Candidate policy {policy} available; independent destination approval required.'
            if changed else 'No candidate available. Review exact scope and channel eligibility.'
        )
    create_transient_feedback(
        status='success' if changed else 'warning',
        title='Scoped routing candidate',
        message=message,
        queue_feedback=True,
    )
    return _redirect(
        url_for('alert_intelligence.index', domain='secrets_pki', provider='vault', asset=instance, tab='routing')
    )


def local_delivery_response(public_id: str) -> ResponseReturnValue:
    actor, instance, binding = _validate({'csrf_token', 'instance_id', 'policy_id', 'channel_id', 'action'})
    intent = DeliveryIntent(instance, binding, actor, public_id, _positive('policy_id'), _positive('channel_id'))
    action = request.form.get('action')
    if action == 'review':
        status = preflight_vault_provider_firing(
            binding_id=binding, instance_id=instance, public_id=public_id, actor_user_id=actor,
            policy_id=intent.policy_id, channel_id=intent.channel_id,
        )
    elif action in ('send', 'retry'):
        status = execute_local_vault_delivery(intent, retry=action == 'retry')
    else:
        abort(400)
    create_transient_feedback(
        status='success' if status == 'sent' else 'info' if status == 'target_qualified' else 'warning',
        title='Scoped delivery review',
        message={
            'sent': 'Provider accepted the explicitly approved delivery.',
            'target_qualified': 'Independent destination receipt qualified. No transport was attempted.',
            'retry_review_required': 'Provider explicitly rejected the attempt. Retry requires a new receipt after the due time.',
            'outcome_review_required': 'Outcome is not confirmed. Automatic replay remains suppressed.',
            'claimed_review_required': 'A durable claim requires review; no replay was attempted.',
        }.get(status, 'Delivery not admitted. Review exact source, policy, channel, approval and journal.'),
        queue_feedback=True,
    )
    return _redirect(
        url_for(
            'alert_intelligence.case_details', public_id=public_id, domain='secrets_pki',
            provider='vault', asset=instance, tab='active'
        )
    )
