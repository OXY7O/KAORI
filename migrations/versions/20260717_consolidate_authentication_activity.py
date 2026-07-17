"""consolidate authentication events into Activity Audit Log

Revision ID: 20260717_auth_activity
Revises: 20260717_google_github_sso
Create Date: 2026-07-17
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from alembic import op

revision = '20260717_auth_activity'
down_revision = '20260717_google_github_sso'
branch_labels = None
depends_on = None


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
    }
    normalized = (reason or '').strip().lower()
    return labels.get(normalized, normalized.replace('_', ' ').title() or 'No reason recorded')


def _parse_user_agent(user_agent: str | None) -> dict[str, str]:
    raw = (user_agent or '').strip()
    if not raw:
        return {
            'browser': 'Unknown browser',
            'operating_system': 'Unknown OS',
            'device_type': 'Unknown device',
        }

    lowered = raw.lower()
    if 'edg/' in lowered or 'edge/' in lowered:
        browser = 'Microsoft Edge'
    elif 'opr/' in lowered or 'opera' in lowered:
        browser = 'Opera'
    elif 'firefox/' in lowered:
        browser = 'Firefox'
    elif 'chrome/' in lowered or 'crios/' in lowered:
        browser = 'Chrome'
    elif 'safari/' in lowered and 'version/' in lowered:
        browser = 'Safari'
    else:
        browser = 'Unknown browser'

    if 'windows nt' in lowered:
        operating_system = 'Windows'
    elif 'mac os x' in lowered or 'macintosh' in lowered:
        operating_system = 'macOS'
    elif 'android' in lowered:
        operating_system = 'Android'
    elif any(marker in lowered for marker in ('iphone', 'ipad', 'ipod')):
        operating_system = 'iOS'
    elif 'linux' in lowered:
        operating_system = 'Linux'
    elif 'cros' in lowered:
        operating_system = 'ChromeOS'
    else:
        operating_system = 'Unknown OS'

    if any(marker in lowered for marker in ('mobile', 'iphone', 'android')):
        device = 'Mobile'
    elif any(marker in lowered for marker in ('ipad', 'tablet')):
        device = 'Tablet'
    else:
        device = 'Desktop'

    return {
        'browser': browser,
        'operating_system': operating_system,
        'device_type': device,
    }


def upgrade() -> None:
    op.alter_column(
        'notifications',
        'user_id',
        existing_type=sa.Integer(),
        nullable=True,
    )

    bind = op.get_bind()
    login_events = sa.table(
        'auth_login_events',
        sa.column('id', sa.Integer()),
        sa.column('username', sa.String()),
        sa.column('user_id', sa.Integer()),
        sa.column('source', sa.String()),
        sa.column('success', sa.Boolean()),
        sa.column('reason', sa.String()),
        sa.column('ip_address', sa.String()),
        sa.column('user_agent', sa.String()),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )
    users = sa.table(
        'users',
        sa.column('id', sa.Integer()),
        sa.column('username', sa.String()),
        sa.column('email', sa.String()),
        sa.column('display_name', sa.String()),
        sa.column('role', sa.String()),
    )
    notifications = sa.table(
        'notifications',
        sa.column('user_id', sa.Integer()),
        sa.column('event_type', sa.String()),
        sa.column('status', sa.String()),
        sa.column('title', sa.String()),
        sa.column('message', sa.String()),
        sa.column('detail', sa.Text()),
        sa.column('action_url', sa.String()),
        sa.column('metadata_json', sa.JSON()),
        sa.column('created_at', sa.DateTime(timezone=True)),
        sa.column('read_at', sa.DateTime(timezone=True)),
    )

    rows = bind.execute(
        sa.select(
            login_events.c.id,
            login_events.c.username,
            login_events.c.user_id,
            login_events.c.source,
            login_events.c.success,
            login_events.c.reason,
            login_events.c.ip_address,
            login_events.c.user_agent,
            login_events.c.created_at,
            users.c.email,
            users.c.display_name,
            users.c.role,
            users.c.username.label('account_username'),
        )
        .select_from(login_events.outerjoin(users, users.c.id == login_events.c.user_id))
        .order_by(login_events.c.id.asc())
    ).mappings()

    for row in rows:
        username = str(row['username'] or row['account_username'] or '').strip()
        identity = username or 'Unknown identity'
        source = str(row['source'] or 'database')
        provider = _provider_label(source)
        success = bool(row['success'])
        reason = str(row['reason'] or '')
        user_agent_info = _parse_user_agent(row['user_agent'])
        display_name = str(row['display_name'] or '').strip() or username or None
        role = str(row['role'] or '').replace('_', ' ').title() or None
        metadata: dict[str, Any] = {
            'audit_schema': 'authentication.v1',
            'access_action': 'login',
            'username': username or None,
            'auth_source': source,
            'authentication_provider': provider,
            'result': 'success' if success else 'failed',
            'result_reason': _reason_label(reason),
            'reason_code': reason,
            'ip_address': row['ip_address'],
            'browser': user_agent_info['browser'],
            'operating_system': user_agent_info['operating_system'],
            'device_type': user_agent_info['device_type'],
            'user_agent': row['user_agent'],
            'actor_display_name': display_name,
            'actor_email': row['email'],
            'actor_role': role,
            'legacy_login_event_id': row['id'],
        }
        bind.execute(
            notifications.insert().values(
                user_id=row['user_id'],
                event_type='authentication',
                status='success' if success else 'error',
                title='User signed in' if success else 'Sign-in attempt failed',
                message=(
                    f'{identity} signed in through {provider}.'
                    if success
                    else f'{identity} could not sign in through {provider}.'
                ),
                detail=(
                    'KAORI verified the identity and established an authenticated web session.'
                    if success
                    else f'KAORI rejected the sign-in attempt. {_reason_label(reason)}.'
                ),
                action_url=None,
                metadata_json=metadata,
                created_at=row['created_at'],
                read_at=row['created_at'],
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM notifications WHERE event_type = 'authentication'"))
    op.alter_column(
        'notifications',
        'user_id',
        existing_type=sa.Integer(),
        nullable=False,
    )
