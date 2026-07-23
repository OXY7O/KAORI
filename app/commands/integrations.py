"""Integration operational commands.

One-shot cutover audit, reconciliation, and factory-reset commands were retired after
canonical runtime cutover. Provider runtime refresh is handled by Celery and the
provider workspaces.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import click
from flask.cli import with_appcontext

from app.integrations.runtime import dispatch_integration_runtime_refresh


@click.command('refresh-integration-runtime')
@click.option('--json-output', is_flag=True, help='Print the refresh result as JSON.')
@with_appcontext
def refresh_integration_runtime_command(json_output: bool) -> None:
    """Queue Kubernetes, Prometheus, and Alertmanager runtime health refreshes."""
    result = dispatch_integration_runtime_refresh()
    if json_output:
        click.echo(json.dumps(result, indent=2, sort_keys=True, default=str))
        return

    click.echo('KAORI integration runtime refresh dispatch')
    click.echo(f'Queued: {result.get("queued", 0)}')
    click.echo(f'Skipped: {result.get("skipped", 0)}')

    providers = result.get('providers')
    if not isinstance(providers, Mapping):
        return

    for provider, raw_detail in providers.items():
        detail: Mapping[str, Any] = (
            raw_detail if isinstance(raw_detail, Mapping) else {}
        )
        click.echo(
            f'- {provider}: {detail.get("queued", 0)} queued, '
            f'{detail.get("skipped", 0)} skipped'
        )
