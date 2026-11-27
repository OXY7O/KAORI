"""Default-disabled authenticated web adapter for scoped Vault operator commands."""

from __future__ import annotations

import os
from typing import Any

from flask import abort, make_response, redirect, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from flask_wtf.csrf import validate_csrf
from wtforms.validators import ValidationError

from app.intelligence.alert_intelligence.vault_operator_service import load_operator_controls, resolve_operator_binding
from app.intelligence.alert_intelligence.vault_provider_admission import _ENABLE_ENV
from app.intelligence.alert_intelligence.vault_provider_operator import apply_vault_provider_operator_action
from app.platform_operations.notifications.service import create_transient_feedback

_WEB_ENABLE_ENV = 'KAORI_VAULT_PROVIDER_CASE_OPERATOR_WEB_ENABLED'


def _enabled() -> bool:
    return os.getenv(_ENABLE_ENV) == 'true' and os.getenv(_WEB_ENABLE_ENV) == 'true'


def _positive(raw: str | None) -> int | None:
    if not raw or not raw.isascii() or not raw.isdecimal() or len(raw) > 18 or raw.startswith('0'):
        return None
    return int(raw)


def operator_controls(*, instance_id: int, public_id: str, expected_event_id: int) -> dict[str, Any] | None:
    if not _enabled():
        return None
    actor_id = getattr(current_user, 'id', None)
    if type(actor_id) is not int:
        return None
    return load_operator_controls(
        instance_id=instance_id, public_id=public_id, expected_event_id=expected_event_id, actor_id=actor_id
    )


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
    binding_id = resolve_operator_binding(instance_id)
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
