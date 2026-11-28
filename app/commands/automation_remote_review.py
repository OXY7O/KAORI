"""Local diagnostics for the non-authorizing remote review candidate (#5186)."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import click
from flask.cli import with_appcontext

from app.access.scope_policy import lock_explicit_permissions
from app.extensions.db import db
from app.infrastructure_automation.credential_scope_target import CREDENTIAL_USE_PERMISSION
from app.infrastructure_automation.remote_job_review import review_enabled
from app.infrastructure_automation.remote_preflight_source import review_remote_source_candidate
from app.infrastructure_automation.remote_preflight_target import diagnose_remote_preflight_target
from app.infrastructure_automation.remote_worker_review import resolve_remote_worker_review
from app.infrastructure_automation.security_review import begin_security_review_transaction
from app.infrastructure_automation.source import AutomationPilotDenied

_PERMISSIONS = {
    'integrations.manage', 'inventory.view', 'jobs.execute', 'secrets_pki.view', CREDENTIAL_USE_PERMISSION,
}


@click.command('automation-remote-review-check', short_help='Diagnose local remote review blockers without execution.')
@click.option('--connection-id', type=click.IntRange(min=1), required=True)
@click.option('--actor-id', type=click.IntRange(min=1), required=True, help='Existing actor to evaluate, not impersonate.')
@click.option('--worker-check', is_flag=True, help='Also inspect the configured local source and signed review receipt.')
@click.option('--source-only', is_flag=True, help='Inspect disabled source-only prerequisites without worker qualification.')
@with_appcontext
def automation_remote_review_check(connection_id: int, actor_id: int, worker_check: bool, source_only: bool) -> None:
    """No JobExecution, grant, signature, provider material or broker action."""
    click.echo('execution_authorized=false')
    if source_only and worker_check:
        raise click.ClickException('source_only_worker_check_not_allowed')
    if not review_enabled():
        raise click.ClickException('local_review_disabled')
    try:
        begin_security_review_transaction()
        if not lock_explicit_permissions(actor_id, _PERMISSIONS):
            raise click.ClickException('actor_permissions_unqualified')
        state, target = diagnose_remote_preflight_target(
            actor_id=actor_id, connection_id=connection_id, now=datetime.now(UTC),
            allow_source_only_diagnostics=source_only,
        )
    except click.ClickException:
        raise
    except Exception:
        raise click.ClickException('committed_review_unavailable') from None
    finally:
        db.session.rollback()
    click.echo(f'target_status={state}')
    if source_only or target is None or target.execution_authorized is not False:
        raise click.ClickException('target_review_blocked')
    if not worker_check:
        click.echo('configured_worker_review=not_checked')
        return

    # No database locks are held across source file inspection. The worker
    # must independently repeat all checks immediately before its own commit.
    worker = os.getenv('KAORI_LOCAL_REMOTE_REVIEW_WORKER', '')
    source_path = os.getenv('KAORI_LOCAL_REMOTE_REVIEW_SOURCE', '')
    if not worker or not source_path.startswith('/'):
        raise click.ClickException('worker_review_configuration_missing')
    try:
        source = review_remote_source_candidate(source_path)
    except AutomationPilotDenied:
        raise click.ClickException('remote_source_unqualified') from None
    click.echo('remote_source=disabled_candidate_checked')
    try:
        evidence = resolve_remote_worker_review(source, target, worker_identity=worker, now=datetime.now(UTC))
    except Exception:
        raise click.ClickException('signed_worker_review_unavailable') from None
    if evidence is None or evidence.execution_authorized is not False:
        raise click.ClickException('signed_worker_review_unqualified')
    click.echo('configured_worker_review=historical_receipt_qualified')
    click.echo('runtime_attestation_verified=false')
