"""Opt-in developer-only local pilot, routed through canonical JobExecution."""
from __future__ import annotations

from pathlib import Path

import click

from app.infrastructure_automation.source import OPERATION_ID, SOURCE_REPOSITORY, verify_localhost_source
from app.infrastructure_automation.tasks import AUTOMATION_QUEUE, collect_localhost_facts
from app.platform_operations.jobs.dispatcher import JobDispatchOptions, enqueue_canonical_job


@click.command("automation-localhost-probe")
@click.option("--source-path", required=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--source-sha", required=True, type=str)
def automation_localhost_probe(source_path: Path, source_sha: str) -> None:
    """Schedule only the exact reviewed local-facts automation operation."""
    try:
        root = verify_localhost_source(str(source_path), source_sha)
        job, created = enqueue_canonical_job(
            task=collect_localhost_facts,
            task_kwargs={"source_path": str(root), "source_sha": source_sha},
            job_type="infrastructure_automation",
            operation="automation_localhost_host_facts",
            queue_name=AUTOMATION_QUEUE,
            workload_class="validation",
            requested_by_user_id=None,
            resource_group="automation:localhost",
            scope_type="linux_host",
            scope_key="localhost:automation-worker",
            parameters={
                "operation_id": OPERATION_ID,
                "repository": SOURCE_REPOSITORY,
                "source_sha": source_sha,
                "inventory_identity": "sample-localhost-only",
            },
            max_attempts=1,
            dispatch_options=JobDispatchOptions(
                require_registered_worker=True,
                soft_time_limit_seconds=150,
                hard_time_limit_seconds=180,
            ),
        )
    except Exception as exc:
        raise click.ClickException(f"Read-only pilot blocked: {type(exc).__name__}") from exc
    click.echo(f"JobExecution {job.public_id}: {'queued' if created else 'attached'}")
