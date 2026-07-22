from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from flask import current_app, request

from app.auth.providers.catalog import provider_label
from app.auth.user_agent import parse_user_agent
from app.extensions import db
from app.models.notification import Notification
from app.models.user import User

AUTHENTICATION_EVENT_TYPE = 'authentication'
AUTHENTICATION_AUDIT_SCHEMA = 'authentication.v1'
AuthenticationAction = Literal['login', 'logout']
AuthenticationResult = Literal['success', 'failed']


def _provider_label(source: str) -> str:
    return provider_label(source)


def _reason_label(reason: str) -> str:
    labels = {
        'success': 'Authentication completed successfully',
        'invalid_credentials': 'The supplied credentials were not accepted',
        'database_unavailable': 'The authentication database was unavailable',
        'user_inactive': 'The KAORI account is inactive',
        'provider_unavailable': 'The external authentication provider was unavailable',
        'identity_not_provisioned': 'The external identity is not provisioned in KAORI',
        'state_mismatch': 'The SSO state was invalid or expired',
        'authorization_denied': 'The external sign-in request was cancelled or denied',
        'authorization_code_missing': 'The SSO callback did not include an authorization code',
        'user_initiated': 'The authenticated user ended the session',
    }
    normalized = (reason or '').strip().lower()
    return labels.get(normalized, normalized.replace('_', ' ').title() or 'No reason recorded')


def record_authentication_activity(
    *,
    action: AuthenticationAction,
    username: str,
    source: str,
    result: AuthenticationResult,
    reason: str,
    user: User | None = None,
) -> None:
    """Persist one login or logout event in the unified Activity Audit Log."""

    normalized_username = username.strip()
    created_at = datetime.now(UTC)
    provider = _provider_label(source)
    identity = normalized_username or 'Unknown identity'
    user_agent = request.headers.get('User-Agent')
    user_agent_info = parse_user_agent(user_agent)
    success = result == 'success'
    is_logout = action == 'logout'

    activity = Notification()
    activity.user_id = user.id if user is not None else None
    activity.event_type = AUTHENTICATION_EVENT_TYPE
    activity.status = 'success' if success else 'error'
    activity.title = 'User signed out' if is_logout else ('User signed in' if success else 'Sign-in attempt failed')
    activity.message = (
        f'{identity} signed out from the KAORI web session.'
        if is_logout
        else (
            f'{identity} signed in through {provider}.'
            if success
            else f'{identity} could not sign in through {provider}.'
        )
    )
    activity.detail = (
        f'The authenticated session established through {provider} was cleared by the user.'
        if is_logout
        else (
            'KAORI verified the identity and established an authenticated web session.'
            if success
            else f'KAORI rejected the sign-in attempt. {_reason_label(reason)}.'
        )
    )
    activity.metadata_json = {
        'audit_schema': AUTHENTICATION_AUDIT_SCHEMA,
        'access_action': action,
        'username': normalized_username or None,
        'auth_source': source,
        'authentication_provider': provider,
        'result': result,
        'result_reason': _reason_label(reason),
        'reason_code': reason,
        'ip_address': request.remote_addr,
        'browser': user_agent_info['browser'],
        'operating_system': user_agent_info['os'],
        'device_type': user_agent_info['device'],
        'user_agent': user_agent,
        'actor_display_name': user.display_label if user is not None else None,
        'actor_email': user.email if user is not None else None,
        'actor_role': user.role_display_name if user is not None else None,
    }
    activity.created_at = created_at
    # Authentication events are audit-only and must not create unread items in
    # the personal notification center.
    activity.read_at = created_at

    try:
        db.session.add(activity)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.warning(
            'Authentication activity could not be persisted.',
            exc_info=True,
        )
