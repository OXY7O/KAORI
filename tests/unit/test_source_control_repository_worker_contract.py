"""Worker uses canonical context and never accepts unbounded credential payloads."""

from __future__ import annotations

from pathlib import Path

from app.integrations.source_control import tasks


def test_worker_registered_as_canonical_task_name():
    assert tasks.sync_source_repositories_task.name == (
        'app.integrations.source_control.tasks.sync_source_repositories'
    )


def test_worker_is_id_only_and_does_not_log_provider_exception():
    source = Path(__file__).resolve().parents[2].joinpath(
        'app/integrations/source_control/tasks.py'
    ).read_text()
    assert 'JobExecutionContext(' in source
    assert 'synchronize_installation(db.session, installation)' in source
    assert 'db.session.rollback()' in source
    assert 'context.checkpoint(' in source
    assert 'context.succeed(' in source
    assert 'except JobCancellationRequested:' in source
    assert 'except Exception:' in source
    assert 'logger.exception(' not in source
    assert 'private_key_pem' not in source
    assert 'webhook_secret' not in source
    assert 'apply_async(' not in source


def test_standard_config_template_reuses_shared_kaori_components():
    file = Path(__file__).resolve().parents[2].joinpath(
        'app/templates/platform_operations/jobs/configuration/definitions/'
        'source_control_repository_sync.html'
    )
    html = file.read_text()
    assert 'components/action_button.html' in html
    assert 'components/operational_section_card.html' in html
    assert 'platform_operations/jobs/configuration/_job_overview.html' in html
    assert 'platform_operations/jobs/configuration/_execution_activity.html' in html
    assert 'policy_form.hidden_tag()' in html
    assert 'hx-post=' in html
    assert '<style' not in html
