"""MinIO operator documentation must follow the source-controlled lifecycle policy."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_minio_readme_tracks_approved_2026_qualification_contract() -> None:
    readme = (ROOT / 'app/integrations/storage/object_storage/providers/minio/README.md').read_text(
        encoding='utf-8'
    )
    contract = (
        ROOT / 'app/definitions/catalogs/integrations/storage/object_storage/contract.yaml'
    ).read_text(encoding='utf-8')
    for expected in (
        'minio-community-policy-v1',
        's3-object-storage-v1',
        'RELEASE.2021-12-29T06-49-06Z',
        'RELEASE.2025-10-15T17-29-55Z',
        'extended_supported',
        'archived_community',
    ):
        assert expected in readme
        assert expected in contract
    assert 'minio-release-2024-08-03' not in readme
    assert 'Source Changed / Sync Required' in readme
    assert 'optional per-bucket versioning' in readme
