from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_manual_job_action_labels_are_compact():
    source = (ROOT / 'app/jobs/configuration.py').read_text()
    for label in ('Sync Inventory', 'Sync TLS', 'Refresh Analytics', 'Refresh Forecast'):
        assert f"'{label}'" in source
    for legacy in ('Sync All Inventory', 'Sync TLS Now', 'Run Analytics Refresh', 'Run Forecast Refresh'):
        assert legacy not in source


def test_execution_history_button_is_compact():
    source = (ROOT / 'app/templates/jobs/configuration/_execution_activity.html').read_text()
    assert '>\n                    Executions\n' in source
    assert 'View All Executions' not in source
