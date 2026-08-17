from app.inventory.object_storage.system_presentation import _provider_label, _status


def test_provider_labels_are_provider_neutral() -> None:
    assert _provider_label('minio') == 'MinIO'
    assert _provider_label('astor') == 'AStor'
    assert _provider_label('s3_compatible') == 'S3-Compatible'
    assert _provider_label('future_vendor') == 'Future Vendor'


def test_system_status_uses_kaori_semantic_tones() -> None:
    assert _status('connected') == ('Ready', 'normal')
    assert _status('blocked') == ('Blocked', 'critical')
    assert _status('unknown') == ('Not Observed', 'unknown')
