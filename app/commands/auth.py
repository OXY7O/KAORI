from __future__ import annotations

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy.exc import SQLAlchemyError

from app.auth.audit import cleanup_login_audit_events, count_login_audit_events_older_than
from app.extensions import db

MIN_LOGIN_AUDIT_RETENTION_DAYS = 1


def _resolve_retention_days(days: int | None) -> int:
    configured_days = current_app.config.get(
        'AUTH_LOGIN_AUDIT_RETENTION_DAYS',
        90,
    )
    retention_days = days if days is not None else int(configured_days or 90)

    if retention_days < MIN_LOGIN_AUDIT_RETENTION_DAYS:
        raise click.ClickException(f'Retention days must be at least {MIN_LOGIN_AUDIT_RETENTION_DAYS}.')

    return retention_days


@click.command(
    'cleanup-login-audit',
    short_help='Remove login audit records older than the configured retention window.',
    help=(
        'Remove old auth_login_events rows using an age-based retention policy. '
        'Use --dry-run first to see how many rows would be removed. The Login Activity UI remains limited to recent records; '  # noqa: E501
        'this command controls actual database retention.'
    ),
)
@click.option(
    '--days',
    type=int,
    default=None,
    help='Retention window in days. Defaults to AUTH_LOGIN_AUDIT_RETENTION_DAYS.',
)
@click.option(
    '--dry-run',
    is_flag=True,
    help='Show how many records match the cleanup policy without deleting anything.',
)
@with_appcontext
def cleanup_login_audit(days: int | None, dry_run: bool) -> None:
    retention_days = _resolve_retention_days(days)

    try:
        matched_count = count_login_audit_events_older_than(retention_days)

        click.echo('Login audit retention cleanup')
        click.echo(f'Retention window: {retention_days} day(s)')
        click.echo(f'Records older than retention: {matched_count}')

        if dry_run:
            click.echo('Dry run only. No records deleted.')
            return

        deleted_count = cleanup_login_audit_events(retention_days)
        click.echo(f'Deleted {deleted_count} login audit record(s).')
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise click.ClickException(f'Login audit cleanup failed: {exc}') from exc
