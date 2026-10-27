from __future__ import annotations

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user

from app.access.rbac.decorators import permission_required
from app.integrations.delivery.notification_channels.forms import (
    get_channel_form_view,
    parse_channel_form,
    validate_channel_input,
)
from app.integrations.delivery.notification_channels.lifecycle import (
    NotificationChannelDeletionBlocked,
    NotificationChannelRetirementBlocked,
    delete_channel,
    retire_channel,
)
from app.integrations.delivery.notification_channels.service import (
    ChannelRegistryFilters,
    DeliveryPagination,
    DeliveryRegistryFilters,
    create_channel,
    get_channel,
    get_notification_channels_payload,
    test_channel,
    update_channel,
)
from app.platform_operations.notifications.feedback import OperationalDeliveryPolicy
from app.platform_operations.notifications.service import create_transient_feedback, record_operational_activity

_WORKSPACE_TABS = {'overview', 'channels', 'delivery'}

notification_channels_bp = Blueprint(
    'notification_channels',
    __name__,
    url_prefix='/integrations/notification-channels',
)


@notification_channels_bp.get('/')
@permission_required('integrations.manage')
def index() -> ResponseReturnValue:
    edit_id = request.args.get('edit', type=int)
    requested_tab = str(request.args.get('tab') or 'overview').strip().lower()
    active_tab = 'channels' if edit_id else (requested_tab if requested_tab in _WORKSPACE_TABS else 'overview')
    payload = get_notification_channels_payload(
        channel_filters=ChannelRegistryFilters(
            page=request.args.get('channel_page', default=1, type=int),
            per_page=request.args.get('channel_per_page', default=5, type=int),
            search=request.args.get('channel_search', ''),
            provider=request.args.get('channel_provider', ''),
            state=request.args.get('channel_state', ''),
            lifecycle=request.args.get('channel_lifecycle', 'active'),
        ),
        include_overview=active_tab == 'overview',
        delivery_filters=DeliveryRegistryFilters(
            pagination=DeliveryPagination(
                page=request.args.get('delivery_page', default=1, type=int),
                per_page=request.args.get('delivery_per_page', default=5, type=int),
            ),
            event_key=request.args.get('delivery_event_key', ''),
            provider=request.args.get('delivery_provider', ''),
            domain=request.args.get('delivery_domain', ''),
            severity=request.args.get('delivery_severity', ''),
            status=request.args.get('delivery_status', ''),
        ),
        can_view_reports=current_user.has_permission('reports.view'),
    )
    edit_channel = get_channel(edit_id) if edit_id else None
    if edit_id and (edit_channel is None or edit_channel.lifecycle_state != 'active'):
        abort(404)
    form_channel = get_channel_form_view(edit_channel) if edit_channel else None
    requested_provider = str(request.args.get('provider') or '').strip().lower()
    supported_provider_keys = {str(provider['key']) for provider in payload['providers']}
    initial_provider = requested_provider if requested_provider in supported_provider_keys else ''
    open_configuration = bool(edit_id or request.args.get('configure') == '1')
    return render_template(
        'integrations/delivery/notification_channels/index.html',
        payload=payload,
        active_tab=active_tab,
        form_channel=form_channel,
        initial_provider=initial_provider,
        open_configuration=open_configuration,
    )


@notification_channels_bp.post('/')
@permission_required('integrations.manage')
def create() -> ResponseReturnValue:
    data = parse_channel_form(request.form)
    errors = validate_channel_input(data)
    if errors:
        _queue_configuration_feedback(errors, provider_key=data.provider_key)
        return redirect(
            url_for(
                'notification_channels.index',
                tab='channels',
                configure=1,
                provider=data.provider_key,
                **_channel_return_query(),
            )
        )
    channel = create_channel(data, user_id=int(current_user.id))
    _record_channel_activity(
        channel.id,
        'created',
        'Notification channel created',
        f'{channel.name} was saved. Run Test Delivery before relying on this channel for automatic delivery.',
        channel_name=channel.name,
        provider_key=channel.provider_key,
    )
    return redirect(url_for('notification_channels.index', tab='channels', **_channel_return_query()))


@notification_channels_bp.post('/<int:channel_id>/update')
@permission_required('integrations.manage')
def update(channel_id: int) -> ResponseReturnValue:
    channel = get_channel(channel_id)
    if channel is None:
        abort(404)
    if channel.lifecycle_state != 'active':
        abort(409)
    data = parse_channel_form(request.form, existing=channel)
    errors = validate_channel_input(data, existing=channel)
    if errors:
        _queue_configuration_feedback(errors, provider_key=channel.provider_key)
        return redirect(
            url_for(
                'notification_channels.index',
                tab='channels',
                edit=channel_id,
                configure=1,
                **_channel_return_query(),
            )
        )
    update_channel(channel, data, user_id=int(current_user.id))
    _record_channel_activity(
        channel.id,
        'updated',
        'Notification channel updated',
        f'{channel.name} configuration was updated. Re-run Test Delivery when destination or credentials changed.',
        channel_name=channel.name,
        provider_key=channel.provider_key,
    )
    return redirect(url_for('notification_channels.index', tab='channels', **_channel_return_query()))


@notification_channels_bp.post('/<int:channel_id>/test')
@permission_required('integrations.manage')
def test(channel_id: int) -> ResponseReturnValue:
    channel = get_channel(channel_id)
    if channel is None:
        abort(404)
    if channel.lifecycle_state != 'active':
        abort(409)
    base_url = str(current_app.config.get('KAORI_PUBLIC_BASE_URL') or '')
    result = test_channel(channel, base_url=base_url)
    _record_channel_activity(
        channel.id,
        'test_succeeded' if result.success else 'test_failed',
        'Notification channel test succeeded' if result.success else 'Notification channel test failed',
        result.message,
        channel_name=channel.name,
        provider_key=channel.provider_key,
        status='success' if result.success else 'error',
    )
    return redirect(url_for('notification_channels.index', tab='channels', **_channel_return_query()))


@notification_channels_bp.post('/<int:channel_id>/retire')
@permission_required('integrations.manage')
def retire(channel_id: int) -> ResponseReturnValue:
    channel = get_channel(channel_id)
    if channel is None:
        abort(404)
    if channel.lifecycle_state != 'active':
        abort(409)
    reason = str(request.form.get('retirement_reason') or '')
    try:
        retire_channel(channel, reason=reason, user_id=int(current_user.id))
    except NotificationChannelRetirementBlocked as exc:
        record_operational_activity(
            user_id=int(current_user.id),
            event_type='integration.notification_channel.retirement_blocked',
            status='warning',
            title='Notification channel retirement blocked',
            message=str(exc),
            action_url=url_for('notification_channels.index', tab='channels'),
            action_label='Review channel dependencies',
            action_icon='shield-alert',
            metadata={'module': 'integrations', 'channel_id': channel_id, 'provider_key': channel.provider_key},
            queue_feedback=True,
            delivery_policy=OperationalDeliveryPolicy.PERSISTENT,
        )
        return redirect(url_for('notification_channels.index', tab='channels', **_channel_return_query()))
    _record_channel_activity(
        channel.id,
        'retired',
        'Notification channel retired',
        f'{channel.name} has been retired; provider delivery is disabled and committed history is retained.',
        channel_name=channel.name,
        provider_key=channel.provider_key,
    )
    return redirect(
        url_for(
            'notification_channels.index',
            tab='channels',
            **{
                **_channel_return_query(),
                'channel_lifecycle': 'retired',
            },
        )
    )


@notification_channels_bp.post('/<int:channel_id>/delete')
@permission_required('integrations.manage')
def delete(channel_id: int) -> ResponseReturnValue:
    channel = get_channel(channel_id)
    if channel is None:
        abort(404)
    if channel.lifecycle_state != 'active':
        abort(409)
    name = channel.name
    provider_key = channel.provider_key
    try:
        delete_channel(channel)
    except NotificationChannelDeletionBlocked as exc:
        record_operational_activity(
            user_id=int(current_user.id),
            event_type='integration.notification_channel.delete_blocked',
            status='warning',
            title='Notification channel deletion blocked',
            message=exc.usage.message,
            action_url=url_for('notification_channels.index', tab='channels'),
            action_label='Review Notification Channels',
            action_icon='shield-alert',
            metadata={
                'module': 'integrations',
                'channel_id': channel_id,
                'channel_name': name,
                'provider_key': provider_key,
            },
            queue_feedback=True,
            delivery_policy=OperationalDeliveryPolicy.PERSISTENT,
        )
        return redirect(url_for('notification_channels.index', tab='channels', **_channel_return_query()))
    record_operational_activity(
        user_id=int(current_user.id),
        event_type='integration.notification_channel.deleted',
        status='success',
        title='Notification channel deleted',
        message=f'{name} was removed from KAORI notification delivery.',
        action_url=url_for('notification_channels.index', tab='channels'),
        action_label='Open Notification Channels',
        action_icon='send',
        metadata={
            'module': 'integrations',
            'channel_id': channel_id,
            'channel_name': name,
            'provider_key': provider_key,
        },
        queue_feedback=True,
        delivery_policy=OperationalDeliveryPolicy.PERSISTENT,
    )
    return redirect(url_for('notification_channels.index', tab='channels', **_channel_return_query()))


def _channel_return_query() -> dict[str, str | int]:
    """Preserve bounded channel registry state across POST/redirect and HTMX."""
    query: dict[str, str | int] = {}
    for name in ('channel_search', 'channel_provider', 'channel_state'):
        value = str(request.form.get(name) or '').strip()[:128]
        if value:
            query[name] = value
    if request.form.get('channel_lifecycle') == 'retired':
        query['channel_lifecycle'] = 'retired'
    for name in ('channel_page', 'channel_per_page'):
        value = request.form.get(name, default=0, type=int)
        if value > 0:
            query[name] = min(value, 1000)
    return query


def _queue_configuration_feedback(errors: list[str], *, provider_key: str) -> None:
    create_transient_feedback(
        status='warning',
        title='Notification channel configuration needs attention',
        message='Review the highlighted channel requirements and submit the configuration again.',
        detail=' '.join(errors),
        action_url=url_for(
            'notification_channels.index',
            tab='channels',
            configure=1,
            provider=provider_key,
        ),
        action_label='Review Channel Configuration',
        action_icon='settings-2',
        queue_feedback=True,
    )


def _record_channel_activity(
    channel_id: int,
    action: str,
    title: str,
    message: str,
    *,
    channel_name: str,
    provider_key: str,
    status: str = 'success',
) -> None:
    record_operational_activity(
        user_id=int(current_user.id),
        event_type=f'integration.notification_channel.{action}',
        status=status,
        title=title,
        message=message,
        action_url=url_for('notification_channels.index', tab='channels'),
        action_label='Open Notification Channels',
        action_icon='send',
        metadata={
            'module': 'integrations',
            'channel_id': channel_id,
            'channel_name': channel_name,
            'provider_key': provider_key,
        },
        queue_feedback=True,
        delivery_policy=OperationalDeliveryPolicy.DECK_ON_FAILURE,
    )
