from __future__ import annotations

from typing import Any

from flask import Blueprint, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from app.access.rbac.decorators import permission_required
from app.intelligence.alert_intelligence.application import (
    apply_case_mutation,
    delete_routing_policy_command,
    reset_template_override_command,
    save_routing_policy_command,
    save_template_override_command,
    send_template_test_command,
    test_render_template_command,
)
from app.intelligence.alert_intelligence.case_state import (
    close_false_positive_alert,
    resume_case_routing,
    retire_source_deleted_case,
    suppress_case_routing,
    withdraw_manual_alert,
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
from app.intelligence.recommendation_alert_commands import (
    create_rule_exception_command,
    promote_recommendation_command,
    revoke_rule_exception_command,
    save_recommendation_alert_policy_command,
)
from app.platform_operations.notifications.service import record_operational_activity

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
        target = str(request.headers.get('HX-Target') or '').strip()
        if target == 'alert-operations-active-records':
            return render_template('intelligence/partials/_alert_ops_active_table.html', payload=payload)
        return render_template('intelligence/partials/_alert_intelligence_page.html', payload=payload)
    return render_template('intelligence/alert_intelligence.html', payload=payload)


@alert_intelligence_bp.get('/cases/<string:public_id>/details')
@permission_required('intelligence.view')
def case_details(public_id: str) -> ResponseReturnValue:
    args = request.args.copy()
    args['case'] = public_id
    if not args.get('tab'):
        args['tab'] = 'active'
    payload = get_alert_intelligence_payload(args)
    if payload.get('selected_case') is None:
        return ('Alert case not found.', 404)
    template = (
        'intelligence/partials/_alert_ops_resolved_case_modal.html'
        if payload.get('tab') == 'resolved'
        else 'intelligence/partials/_alert_ops_case_workspace.html'
    )
    return render_template(
        template,
        payload=payload,
        modal_refresh=False,
    )


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
        event_type='alert_case_acknowledged',
        success_title='Alert acknowledged',
        success_message='KAORI recorded operator ownership. Normal repeat delivery resumes when the acknowledgement reminder window expires if the alert is still firing.',
        operation=lambda case: acknowledge_case(case, actor_user_id=_actor_user_id()),
    )


@alert_intelligence_bp.post('/cases/<string:public_id>/assign')
@permission_required('intelligence.decisions.create')
def assign(public_id: str) -> ResponseReturnValue:
    try:
        owner_id = _optional_positive_int(request.form.get('owner_user_id'))
    except ValueError as exc:
        _queue_intelligence_activity(
            event_type='alert_case_owner_update_failed',
            status='error',
            title='Alert owner not updated',
            message=str(exc),
            delivery_policy='deck_on_failure',
            metadata={'case_id': public_id},
        )
        return _redirect(tab='active', case_id=public_id)
    return _case_mutation(
        public_id,
        event_type='alert_case_owner_updated',
        success_title='Alert owner updated',
        success_message='The alert case ownership assignment was updated.',
        operation=lambda case: assign_case(case, owner_user_id=owner_id, actor_user_id=_actor_user_id()),
        after_commit=lambda case: _notify_alert_case_assignment(case, owner_id),
    )


@alert_intelligence_bp.post('/cases/<string:public_id>/mitigating')
@permission_required('intelligence.decisions.create')
def mitigating(public_id: str) -> ResponseReturnValue:
    note = str(request.form.get('note') or '').strip() or None
    return _case_mutation(
        public_id,
        event_type='alert_case_mitigating',
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
        event_type='alert_case_silenced',
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
        event_type='alert_case_unsilenced',
        success_title='Alert delivery resumed',
        success_message='KAORI repeat delivery is eligible again if the alert remains firing.',
        operation=lambda case: revoke_delivery_silence(case, actor_user_id=_actor_user_id()),
    )


@alert_intelligence_bp.post('/cases/<string:public_id>/routing/suppress')
@permission_required('intelligence.decisions.create')
def suppress_routing(public_id: str) -> ResponseReturnValue:
    reason = str(request.form.get('reason') or '').strip()
    return _case_mutation(
        public_id,
        event_type='alert_case_routing_suppressed',
        success_title='Alert routing suppressed',
        success_message='The alert remains active, but KAORI will not route channel notifications until routing is resumed.',
        operation=lambda case: suppress_case_routing(
            case,
            reason='manual',
            note=reason,
            actor_user_id=_actor_user_id(),
        ),
    )


@alert_intelligence_bp.post('/cases/<string:public_id>/routing/resume')
@permission_required('intelligence.decisions.create')
def resume_routing(public_id: str) -> ResponseReturnValue:
    return _case_mutation(
        public_id,
        event_type='alert_case_routing_resumed',
        success_title='Alert routing resumed',
        success_message='The alert is eligible for governed notification routing again while the source remains firing.',
        operation=lambda case: resume_case_routing(case, actor_user_id=_actor_user_id()),
    )


@alert_intelligence_bp.post('/cases/<string:public_id>/withdraw')
@permission_required('intelligence.decisions.create')
def withdraw(public_id: str) -> ResponseReturnValue:
    reason = str(request.form.get('reason') or '').strip()
    return _case_mutation(
        public_id,
        event_type='alert_case_withdrawn',
        success_title='Manual alert withdrawn',
        success_message='The AlertCase was closed as Withdrawn without claiming source resolution. Automatic re-promotion stays suppressed until the finding clears.',
        operation=lambda case: withdraw_manual_alert(
            case,
            reason=reason,
            actor_user_id=_actor_user_id(),
        ),
        tab='resolved',
    )


@alert_intelligence_bp.post('/cases/<string:public_id>/false-positive')
@permission_required('intelligence.decisions.create')
def false_positive(public_id: str) -> ResponseReturnValue:
    reason = str(request.form.get('reason') or '').strip()
    return _case_mutation(
        public_id,
        event_type='alert_case_false_positive',
        success_title='Alert closed as false positive',
        success_message='The case was closed without claiming source recovery. Re-promotion remains suppressed until the finding clears.',
        operation=lambda case: close_false_positive_alert(
            case,
            reason=reason,
            actor_user_id=_actor_user_id(),
        ),
        tab='resolved',
    )


@alert_intelligence_bp.post('/cases/<string:public_id>/retire-source')
@permission_required('intelligence.decisions.create')
def retire_source(public_id: str) -> ResponseReturnValue:
    reason = str(request.form.get('reason') or '').strip()
    return _case_mutation(
        public_id,
        event_type='alert_case_source_retired',
        success_title='Source-deleted alert retired',
        success_message='The case was retained as historical evidence and closed with a Source Decommissioned disposition.',
        operation=lambda case: retire_source_deleted_case(
            case,
            reason=reason,
            actor_user_id=_actor_user_id(),
        ),
        tab='resolved',
    )


@alert_intelligence_bp.post('/cases/<string:public_id>/close')
@permission_required('intelligence.decisions.create')
def close(public_id: str) -> ResponseReturnValue:
    steps = [value.strip() for value in request.form.getlist('remediation_step') if value.strip()]
    if not steps:
        steps = [line.strip() for line in str(request.form.get('remediation_steps') or '').splitlines() if line.strip()]
    return _case_mutation(
        public_id,
        event_type='alert_case_closed',
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
        tab='resolved',
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
        event_type='alert_case_postmortem_updated',
        success_title='Postmortem updated',
        success_message='KAORI saved the incident learning record and action-item evidence.',
        operation=lambda case: save_postmortem(
            case,
            payload=payload,
            complete=complete,
            actor_user_id=_actor_user_id(),
        ),
        tab='resolved',
    )


@alert_intelligence_bp.post('/recommendations/<path:recommendation_key>/promote')
@permission_required('intelligence.decisions.create')
def promote_recommendation_alert(recommendation_key: str) -> ResponseReturnValue:
    try:
        case = promote_recommendation_command(recommendation_key, actor_user_id=_actor_user_id())
    except (ValueError, SQLAlchemyError) as exc:
        _queue_intelligence_activity(
            event_type='recommendation_alert_promotion_failed',
            status='error',
            title='Recommendation Not Promoted',
            message=str(exc),
            delivery_policy='deck_on_failure',
            metadata={'recommendation_key': recommendation_key},
        )
        return redirect(url_for('intelligence.recommendations', q=recommendation_key))
    _queue_intelligence_activity(
        event_type='recommendation_alert_promoted',
        status='success',
        title='Recommendation Promoted',
        message='The finding is now managed through the Alert Intelligence lifecycle.',
        action_url=url_for(
            'alert_intelligence.index',
            tab='active',
            domain=case.domain,
            asset=case.asset_key or 'all',
            case=case.public_id,
        ),
        metadata={'case_id': case.public_id, 'recommendation_key': recommendation_key},
    )
    return redirect(
        url_for(
            'alert_intelligence.index',
            tab='active',
            domain=case.domain,
            asset=case.asset_key or 'all',
            case=case.public_id,
        )
    )


@alert_intelligence_bp.post('/recommendation-policies/<path:rule_key>')
@permission_required('intelligence.decisions.create')
def save_recommendation_alert_policy(rule_key: str) -> ResponseReturnValue:
    try:
        save_recommendation_alert_policy_command(
            rule_key=rule_key,
            eligible=request.form.get('eligible') == '1',
            mode=str(request.form.get('mode') or 'manual'),
            stability_window_minutes=int(str(request.form.get('stability_window_minutes') or '10')),
            minimum_occurrences=int(str(request.form.get('minimum_occurrences') or '2')),
            grouping_mode=str(request.form.get('grouping_mode') or 'finding'),
            actor_user_id=_actor_user_id(),
        )
    except (ValueError, SQLAlchemyError) as exc:
        _queue_intelligence_activity(
            event_type='recommendation_alert_policy_update_failed',
            status='error',
            title='Alert Escalation Policy Not Saved',
            message=str(exc),
            delivery_policy='deck_on_failure',
            metadata={'rule_key': rule_key},
        )
    else:
        _queue_intelligence_activity(
            event_type='recommendation_alert_policy_updated',
            status='success',
            title='Alert Escalation Policy Saved',
            message='Recommendation findings will follow the updated Alert Intelligence promotion policy.',
            action_url=url_for('intelligence.catalog', q=rule_key),
            metadata={'rule_key': rule_key},
        )
    return redirect(url_for('intelligence.catalog', q=rule_key))


@alert_intelligence_bp.post('/rule-exceptions/<path:rule_key>')
@permission_required('intelligence.decisions.create')
def create_rule_exception_for_rule(rule_key: str) -> ResponseReturnValue:
    actor_user_id = _actor_user_id()
    try:
        owner_user_id = _optional_positive_int(request.form.get('owner_user_id'))
        row, stats = create_rule_exception_command(
            rule_key=rule_key,
            asset_key=str(request.form.get('asset_key') or ''),
            scope_mode=str(request.form.get('scope_mode') or 'finding_keys'),
            finding_keys=[str(value) for value in request.form.getlist('finding_keys')],
            reason=str(request.form.get('reason') or ''),
            risk_reference=str(request.form.get('risk_reference') or '') or None,
            expires_in_days=int(str(request.form.get('expires_in_days') or '90')),
            actor_user_id=actor_user_id,
            owner_user_id=owner_user_id,
        )
    except (ValueError, SQLAlchemyError) as exc:
        _queue_intelligence_activity(
            event_type='rule_exception_create_failed',
            status='error',
            title='Accepted Risk Not Created',
            message=str(exc),
            delivery_policy='deck_on_failure',
            metadata={'rule_key': rule_key},
        )
    else:
        reference = str(row.risk_reference or row.public_id)
        _queue_intelligence_activity(
            event_type='rule_exception_created',
            status='success',
            title='Accepted Risk Created',
            message=(
                f'{reference} covers {stats["covered"]} active finding(s); '
                f'{stats["cases_closed"]} fully covered Alert Case(s) were closed.'
            ),
            action_url=url_for('intelligence.catalog', q=rule_key),
            metadata={
                'rule_key': rule_key,
                'rule_exception_id': row.public_id,
                'owner_user_id': row.owner_user_id,
                'risk_reference': reference,
                'covered_findings': stats['covered'],
            },
        )
        if row.owner_user_id is not None:
            record_operational_activity(
                user_id=row.owner_user_id,
                event_type='rule_exception_assigned',
                status='info',
                title='Accepted Risk Assigned',
                message=f'{reference} is assigned to you for follow-up before expiry.',
                detail='Review remediation progress, expiry, and the covered findings before the accepted-risk window closes.',
                action_url=url_for('intelligence.catalog', q=rule_key),
                metadata={
                    'module': 'Intelligence',
                    'rule_key': rule_key,
                    'rule_exception_id': row.public_id,
                    'risk_reference': reference,
                    'work_inbox': True,
                },
                queue_feedback=False,
                delivery_policy='persistent',
            )
    return redirect(url_for('intelligence.catalog', q=rule_key))


@alert_intelligence_bp.post('/rule-exceptions/<string:exception_public_id>/revoke')
@permission_required('intelligence.decisions.create')
def revoke_rule_exception_for_rule(exception_public_id: str) -> ResponseReturnValue:
    rule_key = str(request.form.get('rule_key') or '')
    owner_user_id: int | None = None
    reference = exception_public_id
    try:
        row, released = revoke_rule_exception_command(
            exception_public_id,
            reason=str(request.form.get('reason') or ''),
            actor_user_id=_actor_user_id(),
        )
        rule_key = row.rule_key
        owner_user_id = row.owner_user_id
        reference = str(row.risk_reference or row.public_id)
    except (ValueError, SQLAlchemyError) as exc:
        _queue_intelligence_activity(
            event_type='rule_exception_revoke_failed',
            status='error',
            title='Accepted Risk Not Revoked',
            message=str(exc),
            delivery_policy='deck_on_failure',
            metadata={'rule_exception_id': exception_public_id, 'rule_key': rule_key},
        )
    else:
        _queue_intelligence_activity(
            event_type='rule_exception_revocation_applied',
            status='success',
            title='Accepted Risk Revoked',
            message=f'{released} active finding(s) return to normal alert eligibility on the next reconcile.',
            action_url=url_for('intelligence.catalog', q=rule_key),
            metadata={'rule_exception_id': row.public_id, 'rule_key': rule_key, 'risk_reference': reference},
        )
        if owner_user_id is not None:
            record_operational_activity(
                user_id=owner_user_id,
                event_type='rule_exception_revoked',
                status='warning',
                title='Accepted Risk Revoked',
                message=f'{reference} is no longer active; uncovered findings can return to alert eligibility.',
                action_url=url_for('intelligence.catalog', q=rule_key),
                metadata={
                    'module': 'Intelligence',
                    'rule_key': rule_key,
                    'rule_exception_id': row.public_id,
                    'risk_reference': reference,
                    'work_inbox': True,
                },
                queue_feedback=False,
                delivery_policy='persistent',
            )
    return redirect(url_for('intelligence.catalog', q=rule_key))


@alert_intelligence_bp.get('/routing/<string:policy_ref>/details')
@permission_required('integrations.manage')
def routing_policy_details(policy_ref: str) -> ResponseReturnValue:
    args = request.args.copy()
    args['tab'] = 'routing'
    if policy_ref != 'new':
        if not policy_ref.isdigit():
            return ('Routing policy not found.', 404)
        args['policy'] = policy_ref
    payload = get_alert_intelligence_payload(args)
    if policy_ref != 'new' and payload.get('selected_policy') is None:
        return ('Routing policy not found.', 404)
    return render_template(
        'intelligence/partials/_alert_ops_routing_editor_modal.html',
        payload=payload,
        selected_policy=payload.get('selected_policy'),
    )


@alert_intelligence_bp.post('/routing/<int:policy_id>/delete')
@permission_required('integrations.manage')
def delete_routing_policy(policy_id: int) -> ResponseReturnValue:
    try:
        changed = delete_routing_policy_command(policy_id=policy_id, actor_user_id=_actor_user_id())
    except SQLAlchemyError as exc:
        _queue_intelligence_activity(
            event_type='alert_routing_policy_delete_failed',
            status='error',
            title='Routing policy not deleted',
            message=str(exc),
            delivery_policy='deck_on_failure',
            metadata={'policy_id': policy_id},
        )
    else:
        _queue_intelligence_activity(
            event_type='alert_routing_policy_deleted' if changed else 'alert_routing_policy_unavailable',
            status='success' if changed else 'warning',
            title='Routing policy deleted' if changed else 'Routing policy unavailable',
            message='The routing policy was removed from governed delivery.'
            if changed
            else 'The selected policy no longer exists.',
            delivery_policy='audit_only' if changed else 'deck_on_failure',
            metadata={'policy_id': policy_id},
        )
    return _redirect(tab='routing')


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
                source_types=request.form.getlist('source_types'),
                channel_ids=channel_ids,
                repeat_interval_minutes=int(str(request.form.get('repeat_interval_minutes') or '60')),
                acknowledgement_timeout_minutes=int(str(request.form.get('acknowledgement_timeout_minutes') or '60')),
                send_resolved=request.form.get('send_resolved') == '1',
                matchers=matchers,
            ),
            actor_user_id=_actor_user_id(),
        )
    except (ValueError, SQLAlchemyError) as exc:
        _queue_intelligence_activity(
            event_type='alert_routing_policy_update_failed',
            status='error',
            title='Routing policy not saved',
            message=str(exc),
            delivery_policy='deck_on_failure',
        )
    else:
        _queue_intelligence_activity(
            event_type='alert_routing_policy_updated',
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
            content_format=str(request.form.get('content_format') or 'plain_text'),
            actor_user_id=_actor_user_id(),
        )
    except (ValueError, SQLAlchemyError) as exc:
        _queue_intelligence_activity(
            event_type='alert_notification_template_save_failed',
            status='error',
            title='Template not saved',
            message=str(exc),
            delivery_policy='deck_on_failure',
        )
    else:
        _queue_intelligence_activity(
            event_type='alert_notification_template_saved',
            status='success',
            title='Notification template saved',
            message='Future Alert Operations delivery will use the updated provider template.',
        )
    return _redirect(tab='templates')


@alert_intelligence_bp.post('/templates/test-render')
@permission_required('integrations.manage')
def test_render_template() -> ResponseReturnValue:
    try:
        subject, body = test_render_template_command(
            provider_key=str(request.form.get('provider_key') or ''),
            event_state=str(request.form.get('event_state') or ''),
            subject_template=str(request.form.get('subject_template') or '') or None,
            body_template=str(request.form.get('body_template') or ''),
            content_format=str(request.form.get('content_format') or 'plain_text'),
        )
    except ValueError as exc:
        _queue_intelligence_activity(
            event_type='alert_notification_template_render_failed',
            status='error',
            title='Template render failed',
            message=str(exc),
            delivery_policy='deck_on_failure',
        )
    else:
        _queue_intelligence_activity(
            event_type='alert_notification_template_rendered',
            status='success',
            title='Template render passed',
            message=f'Canonical sample rendered successfully: {subject[:120]} · {len(body)} body characters.',
        )
    return _redirect(tab='templates')


@alert_intelligence_bp.post('/templates/send-test')
@permission_required('integrations.manage')
def send_template_test() -> ResponseReturnValue:
    try:
        channel_id = _optional_positive_int(request.form.get('test_channel_id'))
        if channel_id is None:
            raise ValueError('Select a validated Notification Channel before Send Test.')
        message = send_template_test_command(
            channel_id=channel_id,
            provider_key=str(request.form.get('provider_key') or ''),
            event_state=str(request.form.get('event_state') or ''),
            subject_template=str(request.form.get('subject_template') or '') or None,
            body_template=str(request.form.get('body_template') or ''),
            content_format=str(request.form.get('content_format') or 'plain_text'),
            actor_user_id=_actor_user_id(),
        )
    except (ValueError, SQLAlchemyError) as exc:
        _queue_intelligence_activity(
            event_type='alert_notification_template_test_failed',
            status='error',
            title='Template test not sent',
            message=str(exc),
            delivery_policy='deck_on_failure',
        )
    else:
        _queue_intelligence_activity(
            event_type='alert_notification_template_test_delivered',
            status='success',
            title='Template test delivered',
            message=message or 'The rendered template was delivered through the selected Notification Channel.',
        )
    return _redirect(tab='templates')


@alert_intelligence_bp.post('/templates/reset')
@permission_required('integrations.manage')
def reset_template() -> ResponseReturnValue:
    provider_key = str(request.form.get('provider_key') or '')
    event_state = str(request.form.get('event_state') or '')
    try:
        changed = reset_template_override_command(
            provider_key=provider_key,
            event_state=event_state,
            actor_user_id=_actor_user_id(),
        )
    except (ValueError, SQLAlchemyError) as exc:
        _queue_intelligence_activity(
            event_type='alert_notification_template_reset_failed',
            status='error',
            title='Template not reset',
            message=str(exc),
            delivery_policy='deck_on_failure',
            metadata={'provider_key': provider_key, 'event_state': event_state},
        )
    else:
        _queue_intelligence_activity(
            event_type='alert_notification_template_reset',
            status='success',
            title='System template restored',
            message=(
                'The custom override was removed and future delivery will use the KAORI system template.'
                if changed
                else 'This provider event already uses the KAORI system template.'
            ),
            metadata={'provider_key': provider_key, 'event_state': event_state},
        )
    return _redirect(tab='templates')


def _case_mutation(
    public_id: str,
    *,
    event_type: str,
    success_title: str,
    success_message: str,
    operation,
    tab: str = 'active',
    after_commit=None,
) -> ResponseReturnValue:
    try:
        case = apply_case_mutation(public_id, operation=operation)
    except (ValueError, SQLAlchemyError) as exc:
        _queue_intelligence_activity(
            event_type=f'{event_type}_failed',
            status='error',
            title='Alert operation not applied',
            message=str(exc),
            delivery_policy='deck_on_failure',
            metadata={'case_id': public_id},
        )
        if _modal_case_htmx_request():
            return _modal_case_response(case_id=public_id)
        if _active_records_htmx_request():
            return _active_records_response(case_id=public_id)
        return _redirect(tab='active', case_id=public_id)
    if case is None:
        _queue_intelligence_activity(
            event_type=f'{event_type}_unavailable',
            status='warning',
            title='Alert case unavailable',
            message='The selected alert case no longer exists.',
            delivery_policy='deck_on_failure',
            metadata={'case_id': public_id},
        )
        if _modal_case_htmx_request():
            return ('Alert case unavailable.', 404)
        if _active_records_htmx_request():
            return _active_records_response()
        return _redirect(tab=tab)

    action_url = url_for(
        'alert_intelligence.index',
        tab=tab,
        domain=case.domain,
        asset=case.asset_key or 'all',
        case=case.public_id,
    )
    _queue_intelligence_activity(
        event_type=event_type,
        status='success',
        title=success_title,
        message=success_message,
        action_url=action_url,
        metadata={'case_id': case.public_id, 'domain': case.domain, 'asset_key': case.asset_key},
    )
    if after_commit is not None:
        after_commit(case)

    if _modal_case_htmx_request():
        return _modal_case_response(case_id=case.public_id, tab=tab)
    if _active_records_htmx_request():
        return _active_records_response(case_id=case.public_id)
    return _redirect(tab=tab, case_id=case.public_id)


def _modal_case_htmx_request() -> bool:
    return request.headers.get('HX-Request') == 'true' and str(
        request.headers.get('HX-Target') or ''
    ).strip().startswith('alert-case-modal-content-')


def _modal_case_response(*, case_id: str, tab: str | None = None) -> ResponseReturnValue:
    args = request.form.copy()
    args['case'] = case_id
    requested_tab = str(tab or request.form.get('tab') or 'active').strip().lower()
    args['tab'] = 'resolved' if requested_tab == 'resolved' else 'active'
    payload = get_alert_intelligence_payload(args)
    if payload.get('selected_case') is None:
        return ('Alert case unavailable.', 404)
    template = (
        'intelligence/partials/_alert_ops_resolved_case_modal.html'
        if payload.get('tab') == 'resolved'
        else 'intelligence/partials/_alert_ops_case_workspace.html'
    )
    response = make_response(
        render_template(
            template,
            payload=payload,
            modal_refresh=True,
        )
    )
    response.headers['HX-Trigger'] = 'alertCaseChanged'
    return response


def _active_records_htmx_request() -> bool:
    return (
        request.headers.get('HX-Request') == 'true'
        and str(request.headers.get('HX-Target') or '').strip() == 'alert-operations-active-records'
    )


def _active_records_response(*, case_id: str | None = None) -> ResponseReturnValue:
    args = request.form.copy()
    args['tab'] = 'active'
    if case_id:
        args['case'] = case_id
    else:
        args.pop('case', None)
    payload = get_alert_intelligence_payload(args)
    return render_template('intelligence/partials/_alert_ops_active_table.html', payload=payload)


def _redirect(*, tab: str, case_id: str | None = None) -> ResponseReturnValue:
    values: dict[str, Any] = {
        'tab': tab,
        'domain': str(request.form.get('domain') or request.args.get('domain') or 'kubernetes'),
        'asset': str(request.form.get('asset') or request.args.get('asset') or 'all'),
    }
    if case_id:
        values['case'] = case_id
    return redirect(url_for('alert_intelligence.index', **values))


def _queue_intelligence_activity(
    *,
    event_type: str,
    status: str,
    title: str,
    message: str,
    detail: str | None = None,
    action_url: str | None = None,
    metadata: dict[str, Any] | None = None,
    delivery_policy: str = 'audit_only',
) -> None:
    record_operational_activity(
        user_id=_actor_user_id(),
        event_type=event_type,
        status=status,
        title=title,
        message=message,
        detail=detail,
        action_url=action_url,
        metadata={'module': 'Intelligence', **(metadata or {})},
        queue_feedback=True,
        delivery_policy=delivery_policy,
    )


def _notify_alert_case_assignment(case, owner_user_id: int | None) -> None:
    if owner_user_id is None:
        return
    record_operational_activity(
        user_id=owner_user_id,
        event_type='alert_case_assigned',
        status='info',
        title='Alert Case Assigned',
        message=f'{case.alert_name} was assigned to you for operational follow-up.',
        detail='Review evidence, acknowledge ownership, track remediation, and close the case only after verification.',
        action_url=url_for(
            'alert_intelligence.index',
            tab='active',
            domain=case.domain,
            asset=case.asset_key or 'all',
            case=case.public_id,
        ),
        metadata={
            'module': 'Intelligence',
            'case_id': case.public_id,
            'domain': case.domain,
            'asset_key': case.asset_key,
            'work_inbox': True,
        },
        queue_feedback=False,
        delivery_policy='persistent',
    )


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
