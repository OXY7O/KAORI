from app.storage_inventory.presentation import _product_label, _status


def test_product_labels_are_provider_neutral() -> None:
    assert _product_label('minio') == 'MinIO'
    assert _product_label('astor') == 'AStor'
    assert _product_label('s3_compatible') == 'S3-Compatible'
    assert _product_label('future_vendor') == 'Future Vendor'


def test_system_status_uses_kaori_semantic_tones() -> None:
    assert _status('connected') == ('Ready', 'normal')
    assert _status('blocked') == ('Blocked', 'critical')
    assert _status('unknown') == ('Not Observed', 'unknown')
