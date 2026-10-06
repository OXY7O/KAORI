from __future__ import annotations

import os

import click
from flask.cli import with_appcontext

from app.access.authentication.password_policy import local_password_policy_error
from app.access.rbac.policy import role_is_access_admin_level
from app.access.rbac.service import seed_default_rbac
from app.extensions.db import db
from app.models import Role, User


def _clean_env_value(value: str | None) -> str:
    return (value or '').strip()


def _validate_admin_password(password: str | None) -> str:
    normalized = _clean_env_value(password)

    if not normalized:
        raise click.ClickException('ADMIN_PASSWORD is not configured')

    policy_error = local_password_policy_error(normalized)
    if policy_error is not None:
        raise click.ClickException(f'ADMIN_PASSWORD policy violation: {policy_error}')

    return normalized


def _active_super_admin_exists() -> bool:
    return (
        User.query.filter(
            User.is_super_admin.is_(True),
            User.account_is_active.is_(True),
            User.deleted_at.is_(None),
        ).first()
        is not None
    )


def _get_admin_role() -> Role | None:
    return Role.query.filter_by(name='admin').first()


def _is_admin_level_user(user: User) -> bool:
    return bool(user.is_super_admin or role_is_access_admin_level(user.role_record))


@click.command(
    'bootstrap-admin',
    short_help='Bootstrap the first local super administrator from ADMIN_* environment values.',
    help=(
        'Bootstrap the first local database-backed break-glass super administrator. '
        'The command reads ADMIN_USERNAME, ADMIN_EMAIL, and ADMIN_PASSWORD from the environment. '
        'It seeds default RBAC data first, refuses to run when an active super administrator already exists, '
        'and never resets an existing password. Use reset-admin-password for explicit credential recovery.'
    ),
)
@with_appcontext
def bootstrap_admin() -> None:
    """Create the first local break-glass super administrator.

    This command is intentionally one-time by default. It refuses to create
    another bootstrap administrator when an active super administrator already
    exists. Use reset-admin-password for explicit credential recovery.
    """

    username = _clean_env_value(os.getenv('ADMIN_USERNAME'))
    email = _clean_env_value(os.getenv('ADMIN_EMAIL'))
    password = os.getenv('ADMIN_PASSWORD')

    if not username:
        raise click.ClickException('ADMIN_USERNAME is not configured')

    if not email:
        raise click.ClickException('ADMIN_EMAIL is not configured')

    password = _validate_admin_password(password)

    seed_default_rbac()

    if _active_super_admin_exists():
        raise click.ClickException(
            'Active super administrator already exists. Refusing to create another bootstrap admin.'
        )

    if User.query.filter(User.username == username, User.deleted_at.is_(None)).first():
        raise click.ClickException(f'Active user with username {username!r} already exists')

    if User.query.filter(User.email == email, User.deleted_at.is_(None)).first():
        raise click.ClickException(f'Active user with email {email!r} already exists')

    admin_role = _get_admin_role()

    user = User()
    user.username = username
    user.email = email
    user.display_name = 'Super Administrator'
    user.role_id = admin_role.id if admin_role else None
    user.account_is_active = True
    user.is_super_admin = True
    user.auth_source = 'database'
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    click.echo(f'Super administrator {username} created')


@click.command(
    'reset-admin-password',
    short_help='Reset a local database admin password explicitly.',
    help=(
        'Reset the password for an existing local database-managed admin or super administrator. '
        'This command does not create users, does not work for LDAP/SSO users, and is intended for controlled recovery only. '  # noqa: E501
        'The new password can come from --password, ADMIN_PASSWORD, or an interactive hidden prompt.'
    ),
)
@click.option(
    '--username',
    envvar='ADMIN_USERNAME',
    required=True,
    help='Existing local admin username to reset. Defaults to ADMIN_USERNAME when available.',
)
@click.option(
    '--password',
    envvar='ADMIN_PASSWORD',
    help='New password. Defaults to ADMIN_PASSWORD when available; prompts securely when omitted.',
)
@with_appcontext
def reset_admin_password(username: str, password: str | None) -> None:
    """Explicitly reset a local database administrator password."""

    username = _clean_env_value(username)
    if not username:
        raise click.ClickException('Username is required')

    if password is None:
        password = click.prompt('New admin password', hide_input=True, confirmation_prompt=True)

    password = _validate_admin_password(password)

    user = User.query.filter(
        User.username == username,
        User.deleted_at.is_(None),
    ).first()

    if user is None:
        raise click.ClickException(f'Active user {username!r} was not found')

    if user.auth_source != 'database':
        raise click.ClickException('Password reset is only supported for database-managed users')

    if not _is_admin_level_user(user):
        raise click.ClickException('Password reset through this command is restricted to admin-level users')

    user.set_password(password)
    db.session.commit()

    click.echo(f'Password reset completed for admin user {username}; existing sessions revoked')
