from __future__ import annotations

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.notification_channels.forms import (
    get_channel_form_view,
    parse_channel_form,
    validate_channel_input,
)
from app.notification_channels.service import (
    create_channel,
    delete_channel,
    get_channel,
    get_notification_channels_payload,
    test_channel,
    update_channel,
)
from app.notifications.service import record_operational_activity
from app.rbac.decorators import permission_required

notification_channels_bp = Blueprint(
    'notification_channels',
    __name__,
    url_prefix='/integrations/notification-channels',
)


@notification_channels_bp.get('/')
@permission_required('settings.manage_integrations')
def index() -> ResponseReturnValue:
    payload = get_notification_channels_payload()
    edit_id = request.args.get('edit', type=int)
    form_channel = get_channel_form_view(get_channel(edit_id)) if edit_id else None
    feedback = str(request.args.get('feedback') or '').strip()
    return render_template(
        'integrations/notification_channels/index.html',
        payload=payload,
        form_channel=form_channel,
        feedback=feedback,
    )


@notification_channels_bp.post('/')
@permission_required('settings.manage_integrations')
def create() -> ResponseReturnValue:
    data = parse_channel_form(request.form)
    errors = validate_channel_input(data)
    if errors:
        return redirect(url_for('notification_channels.index', feedback='; '.join(errors)))
    channel = create_channel(data, user_id=int(current_user.id))
    _record_channel_activity(
        channel.id,
        'created',
        'Notification channel created',
        f'{channel.name} is available for testing.',
    )
    return redirect(
        url_for(
            'notification_channels.index',
            feedback='Channel created. Test delivery before relying on it.',
        )
    )


@notification_channels_bp.post('/<int:channel_id>/update')
@permission_required('settings.manage_integrations')
def update(channel_id: int) -> ResponseReturnValue:
    channel = get_channel(channel_id)
    if channel is None:
        abort(404)
    data = parse_channel_form(request.form, existing=channel)
    errors = validate_channel_input(data, existing=channel)
    if errors:
        return redirect(url_for('notification_channels.index', edit=channel_id, feedback='; '.join(errors)))
    update_channel(channel, data, user_id=int(current_user.id))
    _record_channel_activity(
        channel.id,
        'updated',
        'Notification channel updated',
        f'{channel.name} configuration was updated.',
    )
    return redirect(url_for('notification_channels.index', feedback='Channel updated.'))


@notification_channels_bp.post('/<int:channel_id>/test')
@permission_required('settings.manage_integrations')
def test(channel_id: int) -> ResponseReturnValue:
    channel = get_channel(channel_id)
    if channel is None:
        abort(404)
    base_url = str(current_app.config.get('KAORI_PUBLIC_BASE_URL') or '')
    result = test_channel(channel, base_url=base_url)
    _record_channel_activity(
        channel.id,
        'test_succeeded' if result.success else 'test_failed',
        'Notification channel test succeeded' if result.success else 'Notification channel test failed',
        result.message,
        status='success' if result.success else 'error',
    )
    return redirect(url_for('notification_channels.index', feedback=result.message))


@notification_channels_bp.post('/<int:channel_id>/delete')
@permission_required('settings.manage_integrations')
def delete(channel_id: int) -> ResponseReturnValue:
    channel = get_channel(channel_id)
    if channel is None:
        abort(404)
    name = channel.name
    delete_channel(channel)
    record_operational_activity(
        user_id=int(current_user.id),
        event_type='integration.notification_channel.deleted',
        status='success',
        title='Notification channel deleted',
        message=f'{name} was removed from KAORI notification delivery.',
        metadata={'module': 'integrations', 'channel_id': channel_id},
    )
    return redirect(url_for('notification_channels.index', feedback='Channel deleted.'))


def _record_channel_activity(
    channel_id: int,
    action: str,
    title: str,
    message: str,
    *,
    status: str = 'success',
) -> None:
    record_operational_activity(
        user_id=int(current_user.id),
        event_type=f'integration.notification_channel.{action}',
        status=status,
        title=title,
        message=message,
        action_url=url_for('notification_channels.index'),
        action_label='Open Notification Channels',
        action_icon='send',
        metadata={'module': 'integrations', 'channel_id': channel_id},
    )
