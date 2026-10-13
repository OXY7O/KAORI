from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.artifact_registry import job_adapter


def test_unconfirmed_empty_dispatch_is_blocked_before_enqueue(monkeypatch) -> None:
    def fail_enqueue(**_kwargs):
        pytest.fail('Unconfirmed empty request must never enqueue reconciliation')

    monkeypatch.setattr(job_adapter, 'enqueue_all_registry_inventory_sync', fail_enqueue)
    for parameters in [
        {'empty_reconciliation': 'confirm', 'confirm_empty_instance_id': '1', 'confirmation_phrase': 'wrong'},
        {'empty_reconciliation': 'confirm', 'confirm_empty_instance_id': '1', 'confirmation_phrase': 'CONFIRM EMPTY'},
        {
            'empty_reconciliation': 'confirm',
            'confirm_empty_instance_id': 'wrong',
            'confirmation_phrase': 'CONFIRM EMPTY',
        },
    ]:
        outcome = job_adapter.dispatch_registry_inventory_sync(
            requested_by_user_id=None,
            trigger_type='manual',
            parameters=parameters,
        )
        assert outcome.status == 'blocked'


def test_authenticated_confirmation_passes_a_single_provider_scope(monkeypatch) -> None:
    captured = {}

    def fake_enqueue(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id=70), True

    monkeypatch.setattr(job_adapter, 'enqueue_all_registry_inventory_sync', fake_enqueue)
    outcome = job_adapter.dispatch_registry_inventory_sync(
        requested_by_user_id=9,
        trigger_type='manual',
        parameters={
            'empty_reconciliation': 'confirm',
            'confirm_empty_instance_id': '12',
            'confirmation_phrase': 'CONFIRM EMPTY',
        },
    )
    assert outcome.status == 'queued'
    assert captured['confirm_empty_instance_id'] == 12
    assert captured['requested_by_user_id'] == 9


def test_scheduled_manual_confirmation_never_reaches_worker(monkeypatch) -> None:
    monkeypatch.setattr(
        job_adapter,
        'enqueue_all_registry_inventory_sync',
        lambda **_kwargs: pytest.fail('Scheduled job must not accept a confirmed-empty request'),
    )
    outcome = job_adapter.dispatch_registry_inventory_sync(
        requested_by_user_id=9,
        trigger_type='scheduled',
        parameters={
            'empty_reconciliation': 'confirm',
            'confirm_empty_instance_id': '12',
            'confirmation_phrase': 'CONFIRM EMPTY',
        },
    )
    assert outcome.status == 'blocked'


def test_committed_reconciliation_requires_two_independent_empty_discoveries() -> None:
    root = Path(__file__).resolve().parents[3]
    sync = (root / 'app/artifact_registry/sync.py').read_text(encoding='utf-8')
    jobs = (root / 'app/artifact_registry/sync_jobs.py').read_text(encoding='utf-8')
    task = (root / 'app/artifact_registry/tasks.py').read_text(encoding='utf-8')
    routes = (root / 'app/platform_operations/jobs/routes.py').read_text(encoding='utf-8')
    template = (
        root / 'app/templates/platform_operations/jobs/configuration/definitions/artifact_registry_inventory_sync.html'
    ).read_text(encoding='utf-8')

    assert 'if existing_projects and not projects and not confirmed_empty:' in sync
    assert "db.session.refresh(state, attribute_names=['last_committed_at'])" in sync
    assert 'previous_committed_at' in sync
    assert 'previous_project_count' in sync
    assert 'confirmation = collector.collect(provider_record)' in sync
    assert 'if confirmation.projects:' in sync
    assert 'discovery_confirmations' in sync
    assert 'confirmed_empty=reconciliation_evidence is not None' in sync
    assert "'empty_reconciliation_evidence'" in sync
    assert "'reconciliation': 'confirmed_empty'" in jobs
    assert "'targets': targets" in jobs
    assert 'len(targets) != 1' in task
    assert 'requested_by_user_id' in task
    assert "job_key == 'artifact_registry.inventory.sync'" in routes
    assert 'manual_form.hidden_tag()' in template
    assert 'CONFIRM EMPTY' in template
    assert 'selected_job.empty_reconciliation_targets' in template
    assert 'selected_job.active_job' in template
