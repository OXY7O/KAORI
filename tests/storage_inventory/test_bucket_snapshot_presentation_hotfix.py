from pathlib import Path


def test_bucket_snapshot_source_and_endpoint_display_contract_are_compact():
    presentation = Path('app/storage_inventory/presentation.py').read_text(encoding='utf-8')
    assert "'source_label': 'Committed Snapshot'" in presentation
    assert 'def _endpoint_display(' in presentation
    assert "'endpoint_display':" in presentation
