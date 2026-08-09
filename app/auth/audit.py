from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from flask import current_app, request

from app.auth.providers.catalog import provider_label
from app.auth.user_agent import parse_user_agent
from app.extensions.db import db
from app.models.notification import Notification
from app.models.user import User

AUTHENTICATION_EVENT_TYPE = 'authentication'
AUTHENTICATION_AUDIT_SCHEMA = 'authentication.v2'
AuthenticationAction = Literal['login', 'logout']
AuthenticationResult = Literal['success', 'failed']


def _bounded_text(value: object, *, limit: int) -> str | None:
    normalized = str(value or '').strip()
    if not normalized:
        return None
    return normalized[:limit]


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
        'access_not_permitted': 'The account did not pass the KAORI session admission policy',
        'state_mismatch': 'The SSO state was invalid or expired',
        'authorization_denied': 'The external sign-in request was cancelled or denied',
        'authorization_code_missing': 'The SSO callback did not include an authorization code',
        'rate_limited': 'The authentication request exceeded the configured rate limit',
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
    """Persist one login or logout event in the unified Activity Audit Log.

    ``user`` is the KAORI account targeted or resolved by the attempt. Actor
    identity fields are populated only after successful authentication (or
    logout), so a failed password attempt is never mislabeled as that user's
    authenticated action.
    """

    normalized_username = _bounded_text(username, limit=255) or ''
    normalized_source = _bounded_text(source, limit=50) or 'unknown'
    normalized_reason = _bounded_text(reason, limit=80) or 'unknown'
    created_at = datetime.now(UTC)
    provider = _provider_label(normalized_source)
    identity = normalized_username or 'Unknown identity'
    raw_user_agent = _bounded_text(request.headers.get('User-Agent'), limit=1024)
    user_agent_info = parse_user_agent(raw_user_agent)
    ip_address = _bounded_text(request.remote_addr, limit=100)
    success = result == 'success'
    is_logout = action == 'logout'
    authenticated_actor = user if user is not None and (success or is_logout) else None

    activity = Notification()
    # Keep failed attempts linked to a resolved target account so Account &
    # Authentication can show attempted access without asserting actor identity.
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
            else f'KAORI rejected the sign-in attempt. {_reason_label(normalized_reason)}.'
        )
    )
    activity.metadata_json = {
        'audit_schema': AUTHENTICATION_AUDIT_SCHEMA,
        'access_action': action,
        'username': normalized_username or None,
        'auth_source': normalized_source,
        'authentication_provider': provider,
        'result': result,
        'result_reason': _reason_label(normalized_reason),
        'reason_code': normalized_reason,
        'ip_address': ip_address,
        'browser': user_agent_info['browser'],
        'operating_system': user_agent_info['os'],
        'device_type': user_agent_info['device'],
        'user_agent': raw_user_agent,
        'request_method': _bounded_text(request.method, limit=12),
        # request.path deliberately excludes the SSO callback query string and
        # therefore never persists authorization codes or provider errors.
        'request_path': _bounded_text(request.path, limit=500),
        'request_endpoint': _bounded_text(request.endpoint, limit=160),
        'target_user_id': user.id if user is not None else None,
        'actor_authenticated': authenticated_actor is not None,
        'actor_user_id': authenticated_actor.id if authenticated_actor is not None else None,
        'actor_display_name': authenticated_actor.display_label if authenticated_actor is not None else None,
        'actor_email': authenticated_actor.email if authenticated_actor is not None else None,
        'actor_role': authenticated_actor.role_display_name if authenticated_actor is not None else None,
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
