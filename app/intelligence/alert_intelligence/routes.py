from __future__ import annotations

from typing import Any

from flask import Blueprint, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.access.rbac.decorators import permission_required
from app.intelligence.alert_intelligence.application import (
    apply_case_mutation,
    save_routing_policy_command,
    save_template_override_command,
)
from app.intelligence.alert_intelligence.lifecycle import (
    acknowledge_case,
    assign_case,
    close_case,
    create_delivery_silence,
    mark_mitigating,
    revoke_delivery_silence,
    save_postmortem,
)
from app.intelligence.alert_intelligence.routing import RoutingPolicyConfig
from app.intelligence.alert_intelligence.service import get_alert_intelligence_payload
from app.platform_operations.notifications.service import queue_transient_feedback

alert_intelligence_bp = Blueprint(
    'alert_intelligence',
    __name__,
    url_prefix='/intelligence/alert-intelligence',
)


@alert_intelligence_bp.get('')
@permission_required('intelligence.view')
def index() -> ResponseReturnValue:
    payload = get_alert_intelligence_payload(request.args)
    if request.headers.get('HX-Request') == 'true':
        return render_template('intelligence/partials/_alert_intelligence_page.html', payload=payload)
    return render_template('intelligence/alert_intelligence.html', payload=payload)


@alert_intelligence_bp.get('/records')
@permission_required('intelligence.view')
def records() -> ResponseReturnValue:
    payload = get_alert_intelligence_payload(request.args)
    return render_template('intelligence/partials/_alert_ops_active_table.html', payload=payload)


@alert_intelligence_bp.post('/cases/<string:public_id>/acknowledge')
@permission_required('intelligence.decisions.create')
def acknowledge(public_id: str) -> ResponseReturnValue:
    return _case_mutation(
        public_id,
        success_title='Alert acknowledged',
        success_message='KAORI recorded operator ownership and paused normal repeat delivery for this case.',
        operation=lambda case: acknowledge_case(case, actor_user_id=_actor_user_id()),
    )


@alert_intelligence_bp.post('/cases/<string:public_id>/assign')
@permission_required('intelligence.decisions.create')
def assign(public_id: str) -> ResponseReturnValue:
    owner_id = _optional_positive_int(request.form.get('owner_user_id'))
    return _case_mutation(
        public_id,
        success_title='Alert owner updated',
        success_message='The alert case ownership assignment was updated.',
        operation=lambda case: assign_case(case, owner_user_id=owner_id, actor_user_id=_actor_user_id()),
    )


@alert_intelligence_bp.post('/cases/<string:public_id>/mitigating')
@permission_required('intelligence.decisions.create')
def mitigating(public_id: str) -> ResponseReturnValue:
    note = str(request.form.get('note') or '').strip() or None
    return _case_mutation(
        public_id,
        success_title='Mitigation started',
        success_message='KAORI recorded that active remediation is in progress.',
        operation=lambda case: mark_mitigating(case, actor_user_id=_actor_user_id(), note=note),
    )


@alert_intelligence_bp.post('/cases/<string:public_id>/silence')
@permission_required('intelligence.decisions.create')
def silence(public_id: str) -> ResponseReturnValue:
    try:
        duration = int(str(request.form.get('duration_minutes') or '60'))
    except ValueError:
        duration = 60
    reason = str(request.form.get('reason') or '').strip()
    return _case_mutation(
        public_id,
        success_title='Alert delivery silenced',
        success_message='KAORI will suppress repeat channel delivery until the silence expires or is revoked.',
        operation=lambda case: create_delivery_silence(
            case,
            duration_minutes=duration,
            reason=reason,
            actor_user_id=_actor_user_id(),
        ),
    )


@alert_intelligence_bp.post('/cases/<string:public_id>/unsilence')
@permission_required('intelligence.decisions.create')
def unsilence(public_id: str) -> ResponseReturnValue:
    return _case_mutation(
        public_id,
        success_title='Alert delivery resumed',
        success_message='KAORI repeat delivery is eligible again if the alert remains firing.',
        operation=lambda case: revoke_delivery_silence(case, actor_user_id=_actor_user_id()),
    )


@alert_intelligence_bp.post('/cases/<string:public_id>/close')
@permission_required('intelligence.decisions.create')
def close(public_id: str) -> ResponseReturnValue:
    steps = [value.strip() for value in request.form.getlist('remediation_step') if value.strip()]
    if not steps:
        steps = [
            line.strip()
            for line in str(request.form.get('remediation_steps') or '').splitlines()
            if line.strip()
        ]
    return _case_mutation(
        public_id,
        success_title='Alert case closed',
        success_message='Resolution evidence was committed. Resolved delivery will use this evidence.',
        operation=lambda case: close_case(
            case,
            resolution_summary=str(request.form.get('resolution_summary') or ''),
            remediation_steps=steps,
            verification_evidence=str(request.form.get('verification_evidence') or ''),
            change_reference=str(request.form.get('change_reference') or '') or None,
            ticket_reference=str(request.form.get('ticket_reference') or '') or None,
            actor_user_id=_actor_user_id(),
        ),
        tab='history',
    )


@alert_intelligence_bp.post('/cases/<string:public_id>/postmortem')
@permission_required('intelligence.decisions.create')
def postmortem(public_id: str) -> ResponseReturnValue:
    payload = {
        key: str(request.form.get(key) or '')
        for key in (
            'impact',
            'timeline_summary',
            'root_cause',
            'trigger',
            'contributing_factors',
            'recovery',
            'went_well',
            'went_poorly',
            'action_items',
            'lessons_learned',
        )
    }
    complete = request.form.get('status') == 'complete'
    return _case_mutation(
        public_id,
        success_title='Postmortem updated',
        success_message='KAORI saved the incident learning record and action-item evidence.',
        operation=lambda case: save_postmortem(
            case,
            payload=payload,
            complete=complete,
            actor_user_id=_actor_user_id(),
        ),
        tab='history',
    )


@alert_intelligence_bp.post('/routing')
@permission_required('integrations.manage')
def save_routing_policy() -> ResponseReturnValue:
    try:
        policy_id = _optional_positive_int(request.form.get('policy_id'))
        channel_ids = [int(value) for value in request.form.getlist('channel_ids') if str(value).isdigit()]
        matchers = _parse_matchers(str(request.form.get('matchers') or ''))
        save_routing_policy_command(
            policy_id=policy_id,
            config=RoutingPolicyConfig(
                name=str(request.form.get('name') or ''),
                enabled=request.form.get('enabled') == '1',
                domains=request.form.getlist('domains'),
                severities=request.form.getlist('severities'),
                channel_ids=channel_ids,
                repeat_interval_minutes=int(str(request.form.get('repeat_interval_minutes') or '60')),
                send_resolved=request.form.get('send_resolved') == '1',
                matchers=matchers,
            ),
            actor_user_id=_actor_user_id(),
        )
    except (ValueError, SQLAlchemyError) as exc:
        queue_transient_feedback(status='error', title='Routing policy not saved', message=str(exc))
    else:
        queue_transient_feedback(
            status='success',
            title='Routing policy saved',
            message='Alert firing/repeat/resolved delivery will use the updated channel policy.',
        )
    return _redirect(tab='routing')


@alert_intelligence_bp.post('/templates')
@permission_required('integrations.manage')
def save_template() -> ResponseReturnValue:
    try:
        save_template_override_command(
            provider_key=str(request.form.get('provider_key') or ''),
            event_state=str(request.form.get('event_state') or ''),
            name=str(request.form.get('name') or ''),
            subject_template=str(request.form.get('subject_template') or '') or None,
            body_template=str(request.form.get('body_template') or ''),
            actor_user_id=_actor_user_id(),
        )
    except (ValueError, SQLAlchemyError) as exc:
        queue_transient_feedback(status='error', title='Template not saved', message=str(exc))
    else:
        queue_transient_feedback(
            status='success',
            title='Notification template saved',
            message='Future Alert Operations delivery will use the updated provider template.',
        )
    return _redirect(tab='templates')


def _case_mutation(
    public_id: str,
    *,
    success_title: str,
    success_message: str,
    operation,
    tab: str = 'active',
) -> ResponseReturnValue:
    try:
        case = apply_case_mutation(public_id, operation=operation)
    except (ValueError, SQLAlchemyError) as exc:
        queue_transient_feedback(status='error', title='Alert operation not applied', message=str(exc))
        return _redirect(tab='active', case_id=public_id)
    if case is None:
        queue_transient_feedback(
            status='error',
            title='Alert case unavailable',
            message='The selected alert case no longer exists.',
        )
        return _redirect(tab=tab)
    queue_transient_feedback(status='success', title=success_title, message=success_message)
    return _redirect(tab=tab, case_id=case.public_id)


def _redirect(*, tab: str, case_id: str | None = None) -> ResponseReturnValue:
    values: dict[str, Any] = {
        'tab': tab,
        'domain': str(request.form.get('domain') or request.args.get('domain') or 'kubernetes'),
        'asset': str(request.form.get('asset') or request.args.get('asset') or 'all'),
    }
    if case_id:
        values['case'] = case_id
    return redirect(url_for('alert_intelligence.index', **values))


def _actor_user_id() -> int | None:
    value = getattr(current_user, 'id', None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_positive_int(value: Any) -> int | None:
    if value in (None, ''):
        return None
    try:
        parsed = int(str(value))
    except ValueError as exc:
        raise ValueError('Selected user or record identifier is invalid.') from exc
    if parsed < 1:
        raise ValueError('Selected user or record identifier is invalid.')
    return parsed


def _parse_matchers(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in value.splitlines():
        normalized = line.strip()
        if not normalized:
            continue
        if '=' not in normalized:
            raise ValueError('Routing matchers must use one key=value pair per line.')
        key, expected = normalized.split('=', 1)
        if not key.strip() or not expected.strip():
            raise ValueError('Routing matchers must use one key=value pair per line.')
        result[key.strip()] = expected.strip().strip('"')
    return result

