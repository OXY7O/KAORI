from __future__ import annotations

import click
from flask.cli import with_appcontext

from app.reports.schedules.service import run_due_schedules


@click.command(
    'run-report-schedules',
    short_help='Run due report schedules and generate report PDFs.',
    help=(
        'Process enabled report schedules whose next_run_at is due. '
        'Use --dry-run to inspect due schedules without creating report records or PDF artifacts.'
    ),
)
@click.option(
    '--limit',
    type=int,
    default=20,
    show_default=True,
    help='Maximum number of due schedules to process in one run.',
)
@click.option(
    '--dry-run',
    is_flag=True,
    help='List due schedules without creating generated reports.',
)
@with_appcontext
def run_report_schedules(limit: int, dry_run: bool) -> None:
    if limit < 1:
        raise click.ClickException('Limit must be at least 1.')

    result = run_due_schedules(
        limit=limit,
        dry_run=dry_run,
    )

    click.echo('Report schedule runner')
    click.echo(f'Checked at: {result["checked_at"].isoformat()}')
    click.echo(f'Dry run: {result["dry_run"]}')
    click.echo(f'Due schedules: {result["due_count"]}')

    for item in result['results']:
        schedule_id = item['schedule_id']
        name = item['name']
        status = item['status']
        message = item.get('message', '')
        report_id = item.get('report_id')
        suffix = f' report_id={report_id}' if report_id else ''
        click.echo(f'- #{schedule_id} {name}: {status}{suffix} {message}'.rstrip())
