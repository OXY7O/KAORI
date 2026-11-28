"""Explicit operator maintenance; never archive or print pending factor material."""

from __future__ import annotations

import json

import click
from flask.cli import with_appcontext
from sqlalchemy.exc import SQLAlchemyError

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
