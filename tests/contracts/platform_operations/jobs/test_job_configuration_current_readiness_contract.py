from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
CONFIGURATION = ROOT / 'app/platform_operations/jobs/configuration.py'
MATERIALIZATION = ROOT / 'app/templates/platform_operations/jobs/configuration/definitions/_materialization_job.html'


def test_selected_job_catalog_status_uses_current_configuration_state() -> None:
    source = CONFIGURATION.read_text(encoding='utf-8')

    assert "selected_context.get('configuration_state')" in source
    assert "item['status'] = dict(" in source
    assert "catalog_row['status'] = dict(" in source


def test_historical_dispatch_block_is_explicitly_historical() -> None:
    source = CONFIGURATION.read_text(encoding='utf-8')
    template = MATERIALIZATION.read_text(encoding='utf-8')

    assert "'label': 'Last Dispatch Blocked'" in source
    assert "'label': 'Dispatch Blocked'" not in source
    assert 'Result:' in template
    assert 'policy.last_dispatch_status' in template
