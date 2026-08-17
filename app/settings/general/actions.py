from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask import url_for

from app.common.timezone import (
    is_valid_timezone_name,
    normalize_date_format,
    normalize_locale,
    normalize_time_format,
    normalize_timezone_mode,
    normalize_timezone_name,
)
from app.extensions.db import db
from app.models import User
from app.notifications.feedback import OperationalDeliveryPolicy
from app.notifications.service import create_transient_feedback, record_operational_activity
from app.settings.general.forms import RegionalFormatForm, TimezonePreferenceForm


@dataclass(slots=True)
class GeneralSettingsActionResult:
    feedback: dict[str, Any] | None = None
    saved: bool = False
    notification_changed: bool = False


def save_timezone_preference(
    *,
    user: User,
    form: TimezonePreferenceForm,
    is_htmx: bool,
) -> GeneralSettingsActionResult:
    if not form.validate_on_submit():
        return GeneralSettingsActionResult(
            feedback=create_transient_feedback(
                status='error',
                title='Time zone preference not saved',
                message='Review the highlighted preference fields before saving again.',
                action_url=url_for('settings.general', tab='time-locale'),
                action_label='Review Time Zone',
                action_icon='map-pinned',
                queue_feedback=not is_htmx,
            )
        )

    timezone_mode = normalize_timezone_mode(form.timezone_mode.data)
    requested_timezone = form.browser_timezone.data if timezone_mode == 'automatic' else form.timezone.data
    if not is_valid_timezone_name(requested_timezone):
        form.timezone.errors = ['The selected or detected browser timezone is not a valid IANA timezone.']
        return GeneralSettingsActionResult(
            feedback=create_transient_feedback(
                status='error',
                title='Time zone preference not saved',
                message='Choose a valid IANA timezone before saving this preference.',
                action_url=url_for('settings.general', tab='time-locale'),
                action_label='Review Time Zone',
                action_icon='map-pinned',
                queue_feedback=not is_htmx,
            )
        )

    user.timezone_mode = timezone_mode
    user.timezone = normalize_timezone_name(requested_timezone)
    db.session.commit()
    feedback = record_operational_activity(
        user_id=user.id,
        event_type='user_preference',
        status='success',
        title='Time Zone Preference Saved',
        message=f'KAORI now renders time-related information for this account using {user.timezone}.',
        action_url=url_for('settings.general', tab='time-locale'),
        action_label='Open General Settings',
        action_icon='settings-2',
        metadata={
            'preference': 'timezone',
            'timezone_mode': user.timezone_mode,
            'timezone': user.timezone,
        },
        queue_feedback=not is_htmx,
        delivery_policy=OperationalDeliveryPolicy.AUDIT_ONLY,
    )
    return GeneralSettingsActionResult(
        feedback=feedback,
        saved=True,
        notification_changed=bool(feedback.get('notification_deck_visible')),
    )


def save_regional_format_preference(
    *,
    user: User,
    form: RegionalFormatForm,
    is_htmx: bool,
) -> GeneralSettingsActionResult:
    if not form.validate_on_submit():
        return GeneralSettingsActionResult(
            feedback=create_transient_feedback(
                status='error',
                title='Regional format preference not saved',
                message='Review the highlighted regional format fields before saving again.',
                action_url=url_for('settings.general', tab='regional-format'),
                action_label='Review Regional Format',
                action_icon='calendar-range',
                queue_feedback=not is_htmx,
            )
        )

    user.locale = normalize_locale(form.locale.data)
    user.date_format = normalize_date_format(form.date_format.data)
    user.time_format = normalize_time_format(form.time_format.data)
    db.session.commit()
    feedback = record_operational_activity(
        user_id=user.id,
        event_type='user_preference',
        status='success',
        title='Regional Format Preference Saved',
        message='Date, time, and locale presentation preferences are now active for this account.',
        action_url=url_for('settings.general', tab='regional-format'),
        action_label='Open General Settings',
        action_icon='settings-2',
        metadata={
            'preference': 'regional_format',
            'locale': user.locale,
            'date_format': user.date_format,
            'time_format': user.time_format,
        },
        queue_feedback=not is_htmx,
        delivery_policy=OperationalDeliveryPolicy.AUDIT_ONLY,
    )
    return GeneralSettingsActionResult(
        feedback=feedback,
        saved=True,
        notification_changed=bool(feedback.get('notification_deck_visible')),
    )
