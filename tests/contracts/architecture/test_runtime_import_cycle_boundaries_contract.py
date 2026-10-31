"""Permanent regression for Kernel, Source Control and Vault Alert task import direction."""

from __future__ import annotations

from pathlib import Path

from app.integrations.source_control import eligibility, sync_jobs, tasks as source_tasks
from app.intelligence.alert_signals import tasks as alert_tasks
from app.intelligence.alert_signals import vault_dispatch, vault_jobs
from app.platform_operations.jobs.registry import get_job_definition

ROOT = Path(__file__).resolve().parents[3]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_kernel_uses_existing_lazy_builtin_loader_without_static_provider_import() -> None:
    source = _source('app/integrations/kernel/registry.py')
    assert "if provider_kind('source_control', 'github').available:" in source
    assert "import_module(" in source
    assert "'app.integrations.source_control.source_control.providers.github.kernel_contract'" in source
    assert 'provider.register_after_admission(self)' in source
    assert 'from app.integrations.source_control.source_control.providers.github.kernel_contract import' not in source


def test_repository_admission_and_worker_share_one_strict_eligibility_predicate() -> None:
    source = _source('app/integrations/source_control/tasks.py')
    assert 'from app.integrations.source_control.eligibility import MAX_INSTALLATIONS, _eligible' in source
    assert 'from app.integrations.source_control.sync_jobs import' not in source
    assert source_tasks._eligible is eligibility._eligible is sync_jobs._eligible
    assert source_tasks.MAX_INSTALLATIONS == sync_jobs.MAX_INSTALLATIONS == eligibility.MAX_INSTALLATIONS == 25


def test_vault_alert_job_registry_points_to_distinct_manual_dispatch_owner() -> None:
    definition = get_job_definition('secrets_pki.vault_alerts.observe')
    assert definition.dispatcher_path == (
        'app.intelligence.alert_signals.vault_dispatch:dispatch_vault_alert_observations'
    )
    assert definition.context_builder_path == (
        'app.intelligence.alert_signals.vault_jobs:build_vault_alert_job_context'
    )
    assert alert_tasks.observe_vault_alert_source.name == (
        'app.intelligence.alert_signals.tasks.observe_vault_alert_source'
    )
    assert vault_dispatch.JOB_TYPE == vault_jobs.JOB_TYPE
    assert vault_dispatch.OPERATION == vault_jobs.OPERATION


def test_vault_alert_worker_and_dispatcher_do_not_import_each_other() -> None:
    task_source = _source('app/intelligence/alert_signals/tasks.py')
    worker_source = _source('app/intelligence/alert_signals/vault_jobs.py')
    dispatch_source = _source('app/intelligence/alert_signals/vault_dispatch.py')
    assert 'from app.intelligence.alert_signals.vault_jobs import run_vault_alert_observation_job' in task_source
    assert 'from app.intelligence.alert_signals.tasks import' not in worker_source
    assert 'from app.intelligence.alert_signals.vault_dispatch import' not in worker_source
    assert 'from app.intelligence.alert_signals.tasks import observe_vault_alert_source' in dispatch_source


def test_manual_vault_dispatch_fails_closed_without_polling_when_no_targets(monkeypatch) -> None:
    monkeypatch.setattr(vault_dispatch, 'build_vault_alert_observation_targets', lambda: [])
    result = vault_dispatch.dispatch_vault_alert_observations(
        requested_by_user_id=3,
        trigger_type='manual',
    )
    assert result.status == 'blocked'
    assert result.job is None
    assert result.created is False
