from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding='utf-8')


def test_minio_2024_quota_parser_does_not_mask_legacy_quota_with_zero_size() -> None:
    client = read('app/integrations/storage/object_storage/providers/minio/client.py')

    assert "for field_name in ('size', 'quota')" in client
    assert "field_name == 'size' and value > 0" in client
    assert "field_name == 'quota' and value > 0" in client
    assert "payload.get('size', payload.get('quota', 0))" not in client
