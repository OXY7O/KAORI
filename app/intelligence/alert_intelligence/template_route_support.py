from __future__ import annotations

from collections.abc import Callable

from flask import request
from sqlalchemy.exc import SQLAlchemyError

from app.intelligence.alert_intelligence.application import (
    reset_template_override_command,
    save_template_override_command,
    send_template_test_command,
    test_render_template_command,
)

ActivityCallback = Callable[..., None]


def handle_save_template(*, queue_activity: ActivityCallback, actor_user_id: int | None) -> None:
    try:
        save_template_override_command(
            provider_key=str(request.form.get('provider_key') or ''),
            event_state=str(request.form.get('event_state') or ''),
            name=str(request.form.get('name') or ''),
            subject_template=str(request.form.get('subject_template') or '') or None,
            body_template=str(request.form.get('body_template') or ''),
            content_format=str(request.form.get('content_format') or 'plain_text'),
            actor_user_id=actor_user_id,
        )
    except (ValueError, SQLAlchemyError) as exc:
        queue_activity(
            event_type='alert_notification_template_save_failed',
            status='error',
            title='Template not saved',
            message=str(exc),
            delivery_policy='deck_on_failure',
        )
    else:
        queue_activity(
            event_type='alert_notification_template_saved',
            status='success',
            title='Notification template saved',
            message='Future Alert Operations delivery will use the updated provider template.',
        )


def handle_test_render_template(*, queue_activity: ActivityCallback) -> None:
    try:
        subject, body = test_render_template_command(
            provider_key=str(request.form.get('provider_key') or ''),
            event_state=str(request.form.get('event_state') or ''),
            subject_template=str(request.form.get('subject_template') or '') or None,
            body_template=str(request.form.get('body_template') or ''),
            content_format=str(request.form.get('content_format') or 'plain_text'),
        )
    except ValueError as exc:
        queue_activity(
            event_type='alert_notification_template_render_failed',
            status='error',
            title='Template render failed',
            message=str(exc),
            delivery_policy='deck_on_failure',
        )
    else:
        queue_activity(
            event_type='alert_notification_template_rendered',
            status='success',
            title='Template render passed',
            message=f'Canonical sample rendered successfully: {subject[:120]} · {len(body)} body characters.',
        )


def handle_send_template_test(
    *,
    queue_activity: ActivityCallback,
    actor_user_id: int | None,
    channel_id: int | None,
) -> None:
    try:
        if channel_id is None:
            raise ValueError('Select a validated Notification Channel before Send Test.')
        message = send_template_test_command(
            channel_id=channel_id,
            provider_key=str(request.form.get('provider_key') or ''),
            event_state=str(request.form.get('event_state') or ''),
            subject_template=str(request.form.get('subject_template') or '') or None,
            body_template=str(request.form.get('body_template') or ''),
            content_format=str(request.form.get('content_format') or 'plain_text'),
            actor_user_id=actor_user_id,
        )
    except (ValueError, SQLAlchemyError) as exc:
        queue_activity(
            event_type='alert_notification_template_test_failed',
            status='error',
            title='Template test not sent',
            message=str(exc),
            delivery_policy='deck_on_failure',
        )
    else:
        queue_activity(
            event_type='alert_notification_template_test_delivered',
            status='success',
            title='Template test delivered',
            message=message or 'The rendered template was delivered through the selected Notification Channel.',
        )


def handle_reset_template(*, queue_activity: ActivityCallback, actor_user_id: int | None) -> None:
    provider_key = str(request.form.get('provider_key') or '')
    event_state = str(request.form.get('event_state') or '')
    try:
        changed = reset_template_override_command(
            provider_key=provider_key,
            event_state=event_state,
            actor_user_id=actor_user_id,
        )
    except (ValueError, SQLAlchemyError) as exc:
        queue_activity(
            event_type='alert_notification_template_reset_failed',
            status='error',
            title='Template not reset',
            message=str(exc),
            delivery_policy='deck_on_failure',
            metadata={'provider_key': provider_key, 'event_state': event_state},
        )
    else:
        queue_activity(
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
