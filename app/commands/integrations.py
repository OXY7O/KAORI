from __future__ import annotations

import json
from pathlib import Path

import click
from flask import current_app
from flask.cli import with_appcontext

from app.integrations.legacy_audit import build_legacy_audit_report


@click.command(
    'audit-integration-legacy',
    short_help='Audit readiness to remove legacy integration schema.',
    help=(
        'Inspect active source references, legacy table data, canonical provider identities, '
        'Kubernetes connection coverage, and canonical binding integrity. The command is read-only.'
    ),
)
@click.option('--json-output', is_flag=True, help='Print the complete report as JSON.')
@click.option(
    '--strict/--no-strict',
    default=True,
    show_default=True,
    help='Return a non-zero exit code when destructive schema removal is not ready.',
)
@with_appcontext
def audit_integration_legacy(json_output: bool, strict: bool) -> None:
    project_root = Path(current_app.root_path).parent
    report = build_legacy_audit_report(project_root)

    if json_output:
        click.echo(json.dumps(report.as_dict(), indent=2, sort_keys=True, default=str))
    else:
        click.echo('KAORI integration legacy cutover audit')
        click.echo(f'Ready for schema removal: {"YES" if report.ready_for_schema_removal else "NO"}')
        click.echo('')
        for check in report.checks:
            label = check.status.upper()
            blocker = ' [BLOCKER]' if check.destructive_blocker else ''
            click.echo(f'[{label}]{blocker} {check.key}: {check.summary}')
            for key, value in check.details.items():
                if value in (None, [], {}, 0):
                    continue
                click.echo(f'  - {key}: {value}')

    if strict and not report.ready_for_schema_removal:
        raise click.ClickException(
            'Legacy integration schema is not ready for destructive removal. Resolve all blockers first.'
        )
