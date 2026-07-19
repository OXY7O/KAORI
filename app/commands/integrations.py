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


@click.command(
    'reconcile-integration-legacy',
    short_help='Reconcile canonical integration data before legacy schema removal.',
    help=(
        'Preview or apply a guarded reconciliation of duplicate canonical identities, legacy provider '
        'bindings/config rows, and the legacy cluster kubeconfig copy. The command defaults to dry-run.'
    ),
)
@click.option('--apply', 'apply_changes', is_flag=True, help='Apply the planned reconciliation transaction.')
@click.option('--yes', is_flag=True, help='Skip the confirmation prompt when --apply is used.')
@click.option('--json-output', is_flag=True, help='Print the reconciliation report as JSON.')
@with_appcontext
def reconcile_integration_legacy(apply_changes: bool, yes: bool, json_output: bool) -> None:
    from app.integrations.legacy_reconcile import build_reconciliation_report

    preview = build_reconciliation_report(apply=False)
    if json_output and not apply_changes:
        click.echo(json.dumps(preview.as_dict(), indent=2, sort_keys=True, default=str))
        return

    click.echo('KAORI integration legacy reconciliation')
    click.echo(f'Can apply safely: {"YES" if preview.can_apply else "NO"}')
    click.echo('')
    for action in preview.actions:
        click.echo(f'[PLAN] {action.action}: {action.subject}')
        for key, value in action.details.items():
            click.echo(f'  - {key}: {value}')
    for blocker in preview.blockers:
        click.echo(f'[BLOCKER] {blocker}')

    if not apply_changes:
        click.echo('')
        click.echo('Dry-run only. Re-run with --apply after reviewing the plan.')
        return
    if not preview.can_apply:
        raise click.ClickException('Reconciliation cannot be applied while blockers remain.')
    if not yes:
        click.confirm('Apply this reconciliation transaction?', abort=True)

    result = build_reconciliation_report(apply=True)
    if not result.applied:
        raise click.ClickException('Reconciliation was not applied.')
    if json_output:
        click.echo(json.dumps(result.as_dict(), indent=2, sort_keys=True, default=str))
    else:
        click.echo('')
        click.echo('Reconciliation applied successfully.')


@click.command(
    'factory-reset-integrations',
    short_help='Delete all integration runtime data and rebuild Kubernetes integrations.',
    help=(
        'Preserve Kubernetes cluster assets, delete Prometheus, Alertmanager, runtime history, canonical and '        'legacy integration records, then recreate one canonical KubernetesConnection and binding per cluster. '        'The command defaults to dry-run.'
    ),
)
@click.option('--apply', 'apply_changes', is_flag=True, help='Apply the cleanup transaction.')
@click.option('--yes', is_flag=True, help='Skip the destructive confirmation prompt.')
@click.option('--json-output', is_flag=True, help='Print the cleanup report as JSON.')
@with_appcontext
def factory_reset_integrations(apply_changes: bool, yes: bool, json_output: bool) -> None:
    from app.integrations.factory_cleanup import build_factory_cleanup_report

    preview = build_factory_cleanup_report(apply=False)
    if json_output and not apply_changes:
        click.echo(json.dumps(preview.as_dict(), indent=2, sort_keys=True, default=str))
        return

    click.echo('KAORI integration factory cleanup')
    click.echo(f'Can apply safely: {"YES" if preview.can_apply else "NO"}')
    click.echo(f'Preserved Kubernetes clusters: {len(preview.preserved_cluster_ids)}')
    click.echo('')
    for action in preview.actions:
        click.echo(f'[PLAN] {action.key}: {action.count}')
        click.echo(f'  - {action.detail}')
    for blocker in preview.blockers:
        click.echo(f'[BLOCKER] {blocker}')

    if not apply_changes:
        click.echo('')
        click.echo('Dry-run only. Re-run with --apply after reviewing the plan.')
        return
    if not preview.can_apply:
        raise click.ClickException('Factory cleanup cannot be applied while blockers remain.')
    if not yes:
        click.confirm(
            'Delete all Prometheus and Alertmanager integrations and rebuild Kubernetes integration records?',
            abort=True,
        )

    result = build_factory_cleanup_report(apply=True)
    if not result.applied:
        raise click.ClickException('Factory cleanup was not applied.')
    if json_output:
        click.echo(json.dumps(result.as_dict(), indent=2, sort_keys=True, default=str))
    else:
        click.echo('')
        click.echo('Integration factory cleanup completed successfully.')
        click.echo(f'Recreated Kubernetes connections: {len(result.recreated_kubernetes_connection_ids)}')
        click.echo('Prometheus and Alertmanager are now empty and ready to be registered again.')
