from __future__ import annotations

from app.models.archive import ArchiveArtifact


def artifact_storage_locator(artifact: ArchiveArtifact) -> dict[str, object]:
    metadata = artifact.metadata_json or {}
    locator = metadata.get('storage_locator')
    return dict(locator) if isinstance(locator, dict) else {}


def estimate_uncompressed_size(record_count: int) -> int:
    return max(1024, int(record_count) * 1024)


def error_text(exc: Exception) -> str:
    return str(exc)[:1000]


def normalize_supplement_path(value: str) -> str:
    clean = str(value or '').strip().lstrip('/').replace('\\', '/')
    parts = [part for part in clean.split('/') if part not in {'', '.', '..'}]
    if not parts or any(part == '..' for part in clean.split('/')):
        raise ValueError('Supplemental archive path is invalid.')
    return '/'.join(parts)
