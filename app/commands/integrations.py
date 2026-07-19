"""Integration operational commands.

One-shot legacy audit, reconciliation, and factory-reset commands were retired after
canonical runtime cutover. Provider runtime refresh is handled by Celery and the
provider workspaces.
"""

from __future__ import annotations

import json

import click
from flask.cli import with_appcontext

from app.integrations.runtime.tasks import refresh_integration_runtime


@click.command('refresh-integration-runtime')
@click.option('--json-output', is_flag=True, help='Print the refresh result as JSON.')
@with_appcontext
def refresh_integration_runtime_command(json_output: bool) -> None:
    """Refresh Kubernetes, Prometheus, and Alertmanager runtime state immediately."""
    result = refresh_integration_runtime.run()
    if json_output:
        click.echo(json.dumps(result, indent=2, sort_keys=True, default=str))
        return
    click.echo('KAORI integration runtime refresh')
    click.echo(f"Refreshed: {result.get('refreshed', 0)}")
    click.echo(f"Failed: {result.get('failed', 0)}")
    for provider, detail in (result.get('providers') or {}).items():
        click.echo(f"- {provider}: {detail.get('refreshed', 0)} refreshed, {detail.get('failed', 0)} failed")
