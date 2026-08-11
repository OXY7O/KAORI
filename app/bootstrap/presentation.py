from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import Flask, request
from flask_login import current_user
from flask_wtf.csrf import generate_csrf

from app.cluster.constants import get_environment_label
from app.cluster.onboarding import build_cluster_onboarding_context
from app.common.navigation import build_navigation_breadcrumb
from app.common.timezone import (
    format_user_date,
    format_user_datetime,
    format_user_time,
    normalize_date_format,
    normalize_locale,
    normalize_time_format,
    normalize_timezone_mode,
    normalize_timezone_name,
)
from app.integrations.navigation import build_integration_navigation_context, integration_endpoint_owner
from app.notifications.feedback import pop_operational_feedback
from app.notifications.service import get_navigation_notification_context

_DEFAULT_PREFERENCES = {
    'timezone_name': 'UTC',
    'locale': 'en-US',
    'date_format': 'day_month_year',
    'time_format': '24h',
}


def _user_time_preferences() -> dict[str, str]:
    if not current_user.is_authenticated:
        return dict(_DEFAULT_PREFERENCES)
    return {
        'timezone_name': normalize_timezone_name(getattr(current_user, 'timezone', 'UTC')),
        'locale': normalize_locale(getattr(current_user, 'locale', 'en-US')),
        'date_format': normalize_date_format(getattr(current_user, 'date_format', 'day_month_year')),
        'time_format': normalize_time_format(getattr(current_user, 'time_format', '24h')),
    }


def _navigation_notifications() -> dict[str, Any]:
    if not current_user.is_authenticated:
        return {
            'items': [],
            'history_items': [],
            'attention_items': [],
            'active_jobs': [],
            'active_count': 0,
            'attention_count': 0,
            'unread_count': 0,
            'total_count': 0,
            'display_limit': 8,
            'job_display_limit': 6,
        }
    return get_navigation_notification_context(
        user_id=current_user.id,
        include_all_jobs=current_user.has_permission('jobs.view'),
    )


def _operational_feedback() -> Any:
    if not current_user.is_authenticated:
        return None
    return pop_operational_feedback()


def register_presentation(app: Flask) -> None:
    """Register global template context and formatting filters."""

    @app.context_processor
    def inject_globals() -> dict[str, Any]:
        preferences = _user_time_preferences()
        timezone_mode = (
            normalize_timezone_mode(getattr(current_user, 'timezone_mode', 'manual'))
            if current_user.is_authenticated
            else 'manual'
        )
        integration_navigation = build_integration_navigation_context(request.endpoint)
        integration_owner = integration_endpoint_owner(request.endpoint)
        return {
            'app_version': app.config['APP_VERSION'],
            'current_year': datetime.now().year,
            'current_timezone': preferences['timezone_name'],
            'current_timezone_mode': timezone_mode,
            'current_locale': preferences['locale'],
            'current_date_format': preferences['date_format'],
            'current_time_format': preferences['time_format'],
            'csrf_token': generate_csrf,
            'load_navigation_notification_context': _navigation_notifications,
            'load_operational_feedback': _operational_feedback,
            'cluster_onboarding': build_cluster_onboarding_context(),
            'navigation_breadcrumb': build_navigation_breadcrumb(
                request.endpoint,
                request.path,
                integration_owner=integration_owner,
            ),
            'integration_navigation': integration_navigation,
        }

    @app.template_filter('environment_name')
    def environment_name_filter(value: Any, empty: str = 'Not specified') -> str:
        return get_environment_label(value, empty=empty)

    @app.template_filter('user_datetime')
    def user_datetime_filter(
        value: Any,
        empty: str = '-',
        include_seconds: bool = False,
        include_timezone: bool = True,
        date_format: str | None = None,
        time_format: str | None = None,
    ) -> str:
        preferences = _user_time_preferences()
        return format_user_datetime(
            value,
            preferences['timezone_name'],
            date_format=date_format or preferences['date_format'],
            time_format=time_format or preferences['time_format'],
            locale=preferences['locale'],
            include_seconds=include_seconds,
            include_timezone=include_timezone,
            empty=empty,
        )

    @app.template_filter('user_date')
    def user_date_filter(value: Any, empty: str = '-') -> str:
        preferences = _user_time_preferences()
        return format_user_date(
            value,
            preferences['timezone_name'],
            date_format=preferences['date_format'],
            locale=preferences['locale'],
            empty=empty,
        )

    @app.template_filter('user_time')
    def user_time_filter(
        value: Any,
        empty: str = '-',
        include_seconds: bool = False,
        include_timezone: bool = True,
    ) -> str:
        preferences = _user_time_preferences()
        return format_user_time(
            value,
            preferences['timezone_name'],
            time_format=preferences['time_format'],
            include_seconds=include_seconds,
            include_timezone=include_timezone,
            empty=empty,
        )
