"""Dedicated automation-queue localhost facts task; no remote or mutation path."""
from __future__ import annotations

from tempfile import TemporaryDirectory
from typing import Any

from celery import shared_task

from app.infrastructure_automation.source import (
    INVENTORY,
    OPERATION_ID,
    SOURCE_REPOSITORY,
    AutomationPilotDenied,
    normalize_facts,
    verify_localhost_source,
)
from app.platform_operations.jobs.execution import JobExecutionContext, JobExecutionUnavailable

AUTOMATION_QUEUE = "automation"


@shared_task(
    name="app.infrastructure_automation.tasks.collect_localhost_facts",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def collect_localhost_facts(
    self: Any, *, source_path: str, source_sha: str, job_execution_id: int
) -> dict[str, str]:
    context = JobExecutionContext(task_id=str(self.request.id), job_execution_id=job_execution_id)
    try:
        root = verify_localhost_source(source_path, source_sha)
        context.start(message="Collecting read-only Linux facts from local automation worker", stage="preflight")
        context.checkpoint(message="Approved exact source and local-only inventory verified", stage="execution")
        try:
            import ansible_runner
        except ImportError as exc:
            raise AutomationPilotDenied("Pinned Ansible Runner dependency is unavailable") from exc
        # Runner event artifacts are transient, not committed KAORI evidence.
        with TemporaryDirectory(prefix="kaori-automation-localhost-") as private_data_dir:
            runner = ansible_runner.run(
                private_data_dir=private_data_dir,
                project_dir=str(root / "ansible/playbooks"),
                playbook="linux_host_facts.yml",
                inventory=str(root / INVENTORY),
                limit="localhost",
                quiet=True,
                timeout=120,
                suppress_env_files=True,
                envvars={
                    "ANSIBLE_CONFIG": str(root / "ansible/ansible.cfg"),
                    "ANSIBLE_HOST_KEY_CHECKING": "True",
                },
            )
            if runner.status != "successful" or runner.rc != 0:
                raise AutomationPilotDenied("Runner did not complete the read-only operation")
            facts = normalize_facts(list(runner.events))
        context.succeed(
            result_type="automation_read_only_host_facts",
            result_summary={
                "repository": SOURCE_REPOSITORY,
                "source_sha": source_sha,
                "operation_id": OPERATION_ID,
                "target": "automation-worker:localhost",
                "environment_attestation": "NOT VERIFIED",
                "changed": False,
                "readback": "ansible-setup-facts",
                "facts": facts,
            },
        )
        return {"status": "succeeded", "operation_id": OPERATION_ID}
    except JobExecutionUnavailable:
        return {"status": "blocked", "operation_id": OPERATION_ID}
    except Exception:
        # Never expose original Runner exceptions, paths, secrets or raw events.
        context.fail(
            "Read-only Ansible pilot failed. Inspect sanitized canonical JobExecution evidence.",
            error_code="automation_pilot_failed",
        )
        return {"status": "failed", "operation_id": OPERATION_ID}
