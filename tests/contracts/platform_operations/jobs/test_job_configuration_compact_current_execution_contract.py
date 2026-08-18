from pathlib import Path

TEMPLATE = Path('app/templates/platform_operations/jobs/configuration/_execution_activity.html')


def test_current_execution_is_compact_status_strip():
    text = TEMPLATE.read_text()
    assert 'Current Execution' in text
    assert 'lg:grid-cols-4' in text
    assert 'Worker Execution In Progress' not in text
    assert 'Operational Control' not in text
    assert 'rounded-lg border border-kaori-primary/20 bg-kaori-soft p-4' not in text


def test_idle_state_hides_progress_bar():
    text = TEMPLATE.read_text()
    assert '{% if active_job %}' in text
    assert 'active_job.progress' in text
    assert "active_job.requester if active_job else '—'" in text


def test_manual_actions_remain_available():
    text = TEMPLATE.read_text()
    assert 'jobs.run_now' in text
    assert 'jobs.executions' in text
    assert 'manual_form.hidden_tag()' in text
