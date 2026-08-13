from app.storage_inventory.presentation import _format_bytes, _format_count


def test_bucket_usage_formatters_are_compact() -> None:
    assert _format_bytes(None) == 'Not Collected'
    assert _format_bytes(1024**3) == '1.00 GiB'
    assert _format_count(None) == 'Not Collected'
    assert _format_count(1234567) == '1,234,567'
