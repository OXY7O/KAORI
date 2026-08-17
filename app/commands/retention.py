from __future__ import annotations

import json

import click
from flask.cli import with_appcontext

from app.platform_operations.data_lifecycle.retention.domains import DOMAIN_FACTORIES, get_archive_domain
from app.platform_operations.data_lifecycle.retention.service import (
    preview_retention,
    purge_expired_archives,
    run_retention_archive,
    verify_archive_artifact,
)


@click.group('archive-retention')
def archive_retention() -> None:
    """Manage archive-first retention workflows."""


@archive_retention.command('preview')
@click.option(
    '--domain', type=click.Choice(sorted(DOMAIN_FACTORIES)), default='operational_activity', show_default=True
)
@with_appcontext
def preview_command(domain: str) -> None:
    preview = preview_retention(domain)
    boundary = preview['boundary']
    policy = preview['policy']

    click.echo(f'Domain: {preview["domain"]}')
    click.echo(f'Source model: {preview["source_model"]}')
    click.echo(f'Retention window: {policy.retention_days} day(s)')
    click.echo(f'Selection time: {boundary.selected_at.isoformat()}')
    click.echo(f'Cutoff: {boundary.cutoff_at.isoformat()}')
    click.echo(f'Eligible records: {boundary.record_count}')
    click.echo(f'Protected unread records: {boundary.protected_record_count}')
    click.echo(f'Boundary record ID: {boundary.maximum_record_id or "-"}')
    click.echo('Preview only. No archive was created and no rows were deleted.')


@archive_retention.command('run')
@click.option(
    '--domain', type=click.Choice(sorted(DOMAIN_FACTORIES)), default='operational_activity', show_default=True
)
@click.option(
    '--cleanup/--archive-only',
    default=False,
    show_default=True,
    help='Delete archived hot rows after archive verification. The default is archive-only.',
)
@with_appcontext
def run_command(domain: str, cleanup: bool) -> None:
    result = run_retention_archive(
        domain_name=domain,
        trigger_type='cli',
        cleanup=cleanup,
    )
    click.echo(json.dumps(result, indent=2, default=str, sort_keys=True))


@archive_retention.command('verify')
@click.argument('archive_id')
@with_appcontext
def verify_command(archive_id: str) -> None:
    result = verify_archive_artifact(archive_id)
    click.echo(json.dumps(result, indent=2, default=str, sort_keys=True))


@archive_retention.command('purge-archives')
@click.option(
    '--domain', type=click.Choice(sorted(DOMAIN_FACTORIES)), default='operational_activity', show_default=True
)
@click.option(
    '--execute', is_flag=True, help='Delete expired archive objects. Without this flag the command is a dry run.'
)
@with_appcontext
def purge_archives_command(domain: str, execute: bool) -> None:
    policy = get_archive_domain(domain).build_policy()
    result = purge_expired_archives(
        domain_name=domain,
        retention_days=policy.archive_retention_days,
        dry_run=not execute,
    )
    click.echo(json.dumps(result, indent=2, default=str, sort_keys=True))
