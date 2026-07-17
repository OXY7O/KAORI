from __future__ import annotations

from datetime import UTC, datetime, timedelta

from flask import current_app, request

from app.extensions import db
from app.models.auth import AuthLoginEvent, parse_user_agent
from app.models.notification import Notification
from app.models.user import User

AUTHENTICATION_EVENT_TYPE = 'authentication'
AUTHENTICATION_AUDIT_SCHEMA = 'authentication.v1'


def _provider_label(source: str) -> str:
    normalized = (source or 'database').strip().lower()
    labels = {
        'database': 'Local Database',
        'local': 'Local Database',
        'ldap': 'LDAP / Active Directory',
        'google_oidc': 'Google OpenID Connect',
        'github_oauth': 'GitHub OAuth',
        'oidc': 'OpenID Connect',
        'saml': 'SAML SSO',
        'sso': 'Single Sign-On',
    }
    return labels.get(normalized, normalized.replace('_', ' ').title())


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


def _authentication_metadata(
    *,
    action: str,
    username: str,
    source: str,
    result: str,
    reason: str,
    user: User | None,
    legacy_login_event_id: int | None = None,
) -> dict[str, object | None]:
    user_agent = request.headers.get('User-Agent')
    user_agent_info = parse_user_agent(user_agent)

    metadata: dict[str, object | None] = {
        'audit_schema': AUTHENTICATION_AUDIT_SCHEMA,
        'access_action': action,
        'username': username or None,
        'auth_source': source,
        'authentication_provider': _provider_label(source),
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
    if legacy_login_event_id is not None:
        metadata['legacy_login_event_id'] = legacy_login_event_id
    return metadata


def _build_login_activity(
    *,
    username: str,
    source: str,
    success: bool,
    reason: str,
    user: User | None,
    legacy_login_event_id: int,
    created_at: datetime,
) -> Notification:
    provider = _provider_label(source)
    identity = username or 'Unknown identity'

    activity = Notification()
    activity.user_id = user.id if user is not None else None
    activity.event_type = AUTHENTICATION_EVENT_TYPE
    activity.status = 'success' if success else 'error'
    activity.title = 'User signed in' if success else 'Sign-in attempt failed'
    activity.message = (
        f'{identity} signed in through {provider}.' if success else f'{identity} could not sign in through {provider}.'
    )
    activity.detail = (
        'KAORI verified the identity and established an authenticated web session.'
        if success
        else f'KAORI rejected the sign-in attempt. {_reason_label(reason)}.'
    )
    activity.metadata_json = _authentication_metadata(
        action='login',
        username=username,
        source=source,
        result='success' if success else 'failed',
        reason=reason,
        user=user,
        legacy_login_event_id=legacy_login_event_id,
    )
    activity.created_at = created_at
    # Authentication records are audit-only. They must not create unread items
    # in the personal notification center.
    activity.read_at = created_at
    return activity


def record_login_attempt(
    *,
    username: str,
    source: str,
    success: bool,
    reason: str,
    user_id: int | None = None,
) -> None:
    normalized_username = username.strip()
    created_at = datetime.now(UTC)

    event = AuthLoginEvent()
    event.username = normalized_username or None
    event.user_id = user_id
    event.source = source
    event.success = success
    event.reason = reason
    # ProxyFix normalizes remote_addr when trusted proxy hops are configured.
    # Do not read X-Forwarded-For directly because clients can spoof it.
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    event.ip_address = ip_address[:100] if ip_address else None
    event.user_agent = user_agent[:500] if user_agent else None
    event.created_at = created_at

    try:
        user = db.session.get(User, user_id) if user_id is not None else None
        db.session.add(event)
        db.session.flush()
        db.session.add(
            _build_login_activity(
                username=normalized_username,
                source=source,
                success=success,
                reason=reason,
                user=user,
                legacy_login_event_id=event.id,
                created_at=created_at,
            )
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.warning(
            'Authentication activity could not be persisted.',
            exc_info=True,
        )


def record_logout(*, user: User, source: str) -> None:
    created_at = datetime.now(UTC)
    provider = _provider_label(source)

    activity = Notification()
    activity.user_id = user.id
    activity.event_type = AUTHENTICATION_EVENT_TYPE
    activity.status = 'success'
    activity.title = 'User signed out'
    activity.message = f'{user.display_label} signed out from the KAORI web session.'
    activity.detail = f'The authenticated session established through {provider} was cleared by the user.'
    activity.metadata_json = _authentication_metadata(
        action='logout',
        username=user.username,
        source=source,
        result='success',
        reason='user_initiated',
        user=user,
    )
    activity.created_at = created_at
    activity.read_at = created_at

    try:
        db.session.add(activity)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.warning(
            'Logout activity could not be persisted.',
            exc_info=True,
        )


def build_login_audit_cutoff(retention_days: int) -> datetime:
    """Return the UTC cutoff timestamp for login audit retention cleanup."""

    return datetime.now(UTC) - timedelta(days=retention_days)


def count_login_audit_events_older_than(retention_days: int) -> int:
    cutoff = build_login_audit_cutoff(retention_days)

    return AuthLoginEvent.query.filter(
        AuthLoginEvent.created_at < cutoff,
    ).count()


def cleanup_login_audit_events(retention_days: int) -> int:
    cutoff = build_login_audit_cutoff(retention_days)

    deleted_count = AuthLoginEvent.query.filter(
        AuthLoginEvent.created_at < cutoff,
    ).delete(
        synchronize_session=False,
    )
    db.session.commit()

    return int(deleted_count or 0)
