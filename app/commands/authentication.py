"""Explicit operator maintenance; never archive or print pending factor material."""

from __future__ import annotations

import json
import sys

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy.exc import SQLAlchemyError

from app.access.authentication.break_glass import recover_bot_protection
from app.access.authentication.mfa.cleanup import MAX_BATCH, cleanup_pending_mfa


@click.command('mfa-pending-cleanup')
@click.option('--execute', is_flag=True, help='Remove invalid pending material. Default is read-only preview.')
@click.option('--limit', type=click.IntRange(1, MAX_BATCH), default=100, show_default=True)
@click.option('--after-id', type=click.IntRange(min=0), default=0, show_default=True)
@with_appcontext
def cleanup_pending_mfa_command(execute: bool, limit: int, after_id: int) -> None:
    """Inspect or remove one bounded page of invalid pending MFA material."""
    try:
        result = cleanup_pending_mfa(execute=execute, limit=limit, after_id=after_id)
    except (SQLAlchemyError, RuntimeError, ValueError) as exc:
        raise click.ClickException('Pending MFA maintenance failed; no successful page result was recorded.') from exc
    click.echo(json.dumps(result, indent=2, sort_keys=True))


@click.command('recover-bot-protection')
@with_appcontext
def recover_bot_protection_command() -> None:
    """Commit an explicitly authorized, CLI-only Bot Protection recovery."""
    if not current_app.config.get('AUTH_BREAK_GLASS_RECOVERY_ALLOWED'):
        raise click.ClickException('Recovery is not authorized for this process.')
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise click.ClickException('An interactive management terminal is required.')

    username = click.prompt('Local Super Admin username')
    operator = click.prompt('Named management operator reference')
    ticket = click.prompt('Incident / Change reference')
    reason = click.prompt('Reason (no sensitive data)')
    click.confirm(
        'Temporarily disable Bot Protection, invalidate prior provider verification, and record the incident?',
        abort=True,
    )
    password = click.prompt('Current password', hide_input=True)
    code = click.prompt('Unused authenticator code', hide_input=True)
    try:
        result = recover_bot_protection(
            username=username, operator=operator, ticket=ticket, reason=reason,
            password=password, code=code, acknowledged=True,
        )
    except (SQLAlchemyError, RuntimeError, ValueError):
        # Do not expose SQL parameters, credentials, or underlying provider errors.
        raise click.ClickException('Recovery did not complete; no successful transition is asserted.') from None
    click.echo(f'Committed Bot Protection result: {result.previous_mode} -> {result.new_mode}')
    click.echo(f'Activity correlation: {result.correlation}')
    click.echo('Restore only through the existing fresh Turnstile verification workflow.')
