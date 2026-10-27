from __future__ import annotations

import gzip
import hashlib
import json
from collections.abc import Callable, Iterator
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from app.models.archive import ArchiveArtifact
from app.platform_operations.data_lifecycle.retention.types import ArchiveBoundary, RetentionPolicy


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


def _write_jsonl_gzip(
    *,
    data_path: Path,
    records,
) -> int:
    written_count = 0
    with gzip.open(data_path, mode='wt', encoding='utf-8', newline='\n', compresslevel=6) as archive_file:
        for record in records:
            archive_file.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(',', ':')))
            archive_file.write('\n')
            written_count += 1
    return written_count



def _iter_archive_record_ids(data_path: Path) -> Iterator[Any]:
    """Yield the exact identities written to the verified archive."""
    with gzip.open(data_path, mode='rt', encoding='utf-8') as archive_file:
        for line_number, line in enumerate(archive_file, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            source = payload.get('source') if isinstance(payload, dict) else None
            record_id = source.get('record_id') if isinstance(source, dict) else None
            if record_id is None:
                raise RuntimeError(f'Archive record on line {line_number} does not contain source.record_id.')
            yield record_id



def _build_archive_file_stem(
    artifact: ArchiveArtifact,
    boundary: ArchiveBoundary,
) -> str:
    range_start = (boundary.range_start or boundary.cutoff_at).strftime('%Y%m%dT%H%M%SZ')
    range_end = (boundary.range_end or boundary.cutoff_at).strftime('%Y%m%dT%H%M%SZ')
    return f'{artifact.domain}-{range_start}-{range_end}-{artifact.id}'



def _sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open('rb') as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()



def _normalize_trigger_type(value: str) -> str:
    normalized = value.strip().lower()
    return normalized if normalized in {'manual', 'scheduled', 'cli'} else 'manual'



def _serialize_policy(policy: RetentionPolicy) -> dict[str, Any]:
    payload = asdict(policy)
    return payload



def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _estimate_archive_size(domain, boundary: ArchiveBoundary, policy: RetentionPolicy) -> int:
    estimator = getattr(domain, 'estimate_uncompressed_bytes', None)
    if callable(estimator):
        estimate = cast(Callable[[ArchiveBoundary, RetentionPolicy], object], estimator)(boundary, policy)
        if isinstance(estimate, (int, float, str)):
            return max(int(estimate or 0), 0)
    return estimate_uncompressed_size(boundary.record_count)
