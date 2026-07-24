from __future__ import annotations

import gzip
import hashlib
import json
import logging
import shutil
from collections.abc import Iterator
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import mkdtemp
from typing import Any

from flask import current_app
from sqlalchemy import or_

from app.extensions.db import db
from app.models.archive import (
    ARCHIVE_STATUS_ARCHIVING,
    ARCHIVE_STATUS_CLEANING,
    ARCHIVE_STATUS_CLEANUP_PARTIAL,
    ARCHIVE_STATUS_EXPIRED,
    ARCHIVE_STATUS_FAILED,
    ARCHIVE_STATUS_PENDING,
    ARCHIVE_STATUS_READY,
    ARCHIVE_STATUS_VERIFYING,
    ArchiveArtifact,
)
from app.retention.domains import get_archive_domain
from app.retention.lock import retention_lock
from app.retention.types import ArchiveBoundary, PartialCleanupError, RetentionPolicy
from app.storage.service import (
    build_artifact_storage,
    build_artifact_storage_for_backend,
    build_storage_locator,
    resolve_app_path,
)

logger = logging.getLogger(__name__)


def _artifact_storage_locator(artifact: ArchiveArtifact) -> dict[str, object]:
    metadata = artifact.metadata_json or {}
    locator = metadata.get('storage_locator')
    return dict(locator) if isinstance(locator, dict) else {}


class ArchiveVerificationError(RuntimeError):
    pass


def preview_retention(domain_name: str) -> dict[str, Any]:
    domain = get_archive_domain(domain_name)
    policy = domain.build_policy()
    boundary = domain.inspect_boundary(policy)

    return {
        'domain': domain.name,
        'source_model': domain.source_model,
        'policy': policy,
        'boundary': boundary,
        'estimated_uncompressed_bytes': _estimate_uncompressed_size(boundary.record_count),
    }


def run_retention_archive(
    *,
    domain_name: str,
    trigger_type: str,
    cleanup: bool,
    triggered_by_user_id: int | None = None,
    celery_task_id: str | None = None,
) -> dict[str, Any]:
    domain = get_archive_domain(domain_name)
    policy = domain.build_policy()
    if not policy.enabled:
        raise RuntimeError(f'Retention is disabled for {domain.name}.')

    with retention_lock(domain.name):
        boundary = domain.inspect_boundary(policy)
        if boundary.record_count <= 0 or boundary.maximum_record_id is None:
            return {
                'status': 'no_data',
                'domain': domain.name,
                'record_count': 0,
                'cleanup_requested': cleanup,
                'message': 'No records matched the retention boundary.',
            }

        artifact = ArchiveArtifact()
        artifact.domain = domain.name
        artifact.source_model = domain.source_model
        artifact.trigger_type = _normalize_trigger_type(trigger_type)
        artifact.operation_mode = 'archive_and_cleanup' if cleanup else 'archive_only'
        artifact.status = ARCHIVE_STATUS_PENDING
        artifact.schema_version = domain.schema_version
        artifact.archive_format = 'jsonl'
        artifact.compression = 'gzip'
        artifact.cutoff_at = boundary.cutoff_at
        artifact.range_start = boundary.range_start
        artifact.range_end = boundary.range_end
        artifact.boundary_record_id = boundary.maximum_record_id
        artifact.record_count = boundary.record_count
        artifact.triggered_by_user_id = triggered_by_user_id
        artifact.celery_task_id = celery_task_id
        artifact.metadata_json = {
            'policy': _serialize_policy(policy),
            'protected_record_count': boundary.protected_record_count,
            'protected_cutoff_at': _isoformat(boundary.protected_cutoff_at),
        }
        db.session.add(artifact)
        db.session.commit()

        return _execute_archive(
            artifact_id=artifact.id,
            domain=domain,
            policy=policy,
            boundary=boundary,
            cleanup=cleanup,
        )


def verify_archive_artifact(archive_id: str) -> dict[str, Any]:
    artifact = db.session.get(ArchiveArtifact, archive_id)
    if artifact is None:
        raise LookupError('Archive record was not found.')
    if not artifact.storage_backend or not artifact.data_object_key or not artifact.manifest_object_key:
        raise ArchiveVerificationError('Archive storage metadata is incomplete.')
    if not artifact.checksum_sha256 or artifact.size_bytes is None:
        raise ArchiveVerificationError('Archive checksum metadata is incomplete.')

    backend = build_artifact_storage_for_backend(
        'archive',
        artifact.storage_backend,
        locator=_artifact_storage_locator(artifact),
    )
    _verify_stored_file(
        backend=backend,
        object_key=artifact.data_object_key,
        expected_size=artifact.size_bytes,
        expected_checksum=artifact.checksum_sha256,
    )
    if artifact.manifest_size_bytes is None or not artifact.manifest_checksum_sha256:
        raise ArchiveVerificationError('Archive manifest checksum metadata is incomplete.')
    _verify_stored_file(
        backend=backend,
        object_key=artifact.manifest_object_key,
        expected_size=artifact.manifest_size_bytes,
        expected_checksum=artifact.manifest_checksum_sha256,
    )

    artifact.verified_at = datetime.now(UTC)
    if artifact.status == ARCHIVE_STATUS_FAILED:
        artifact.status = ARCHIVE_STATUS_CLEANUP_PARTIAL if artifact.cleanup_deleted_count > 0 else ARCHIVE_STATUS_READY
    artifact.error_message = None
    db.session.commit()

    return {
        'archive_id': artifact.id,
        'status': 'verified',
        'checksum_sha256': artifact.checksum_sha256,
        'size_bytes': artifact.size_bytes,
    }


def get_archive_download_path(
    archive_id: str,
    *,
    kind: str = 'data',
) -> tuple[ArchiveArtifact, Path]:
    artifact = db.session.get(ArchiveArtifact, archive_id)
    if artifact is None:
        raise LookupError('Archive record was not found.')
    if not artifact.is_downloadable:
        raise RuntimeError('Archive is not ready for download.')
    if not artifact.storage_backend:
        raise RuntimeError('Archive storage backend is missing.')

    normalized_kind = kind.strip().lower()
    if normalized_kind == 'manifest':
        object_key = artifact.manifest_object_key
    else:
        normalized_kind = 'data'
        object_key = artifact.data_object_key

    if not object_key:
        raise RuntimeError(f'Archive {normalized_kind} object key is missing.')

    backend = build_artifact_storage_for_backend(
        'archive',
        artifact.storage_backend,
        locator=_artifact_storage_locator(artifact),
    )
    return artifact, backend.build_download_path(object_key)


def list_archives(
    *,
    domain_name: str,
    limit: int = 10,
) -> list[ArchiveArtifact]:
    normalized_limit = max(1, min(limit, 100))
    return (
        ArchiveArtifact.query.filter(ArchiveArtifact.domain == domain_name)
        .order_by(ArchiveArtifact.created_at.desc(), ArchiveArtifact.id.desc())
        .limit(normalized_limit)
        .all()
    )


def paginate_archives(
    *,
    domain_name: str | None,
    page: int = 1,
    per_page: int = 5,
    status: str = 'all',
    trigger_type: str = 'all',
    operation_mode: str = 'all',
    storage_backend: str = 'all',
    search: str = '',
):
    normalized_page = max(int(page or 1), 1)
    normalized_per_page = int(per_page or 5)
    if normalized_per_page not in {5, 10, 25, 50}:
        normalized_per_page = 5

    query = ArchiveArtifact.query
    if domain_name:
        query = query.filter(ArchiveArtifact.domain == domain_name)

    if status != 'all':
        query = query.filter(ArchiveArtifact.status == status)
    if trigger_type != 'all':
        query = query.filter(ArchiveArtifact.trigger_type == trigger_type)
    if operation_mode != 'all':
        query = query.filter(ArchiveArtifact.operation_mode == operation_mode)
    if storage_backend != 'all':
        query = query.filter(ArchiveArtifact.storage_backend == storage_backend)

    normalized_search = str(search or '').strip()
    if normalized_search:
        pattern = f'%{normalized_search}%'
        query = query.filter(
            or_(
                ArchiveArtifact.id.ilike(pattern),
                ArchiveArtifact.celery_task_id.ilike(pattern),
                ArchiveArtifact.error_message.ilike(pattern),
                ArchiveArtifact.data_object_key.ilike(pattern),
                ArchiveArtifact.manifest_object_key.ilike(pattern),
            )
        )

    return query.order_by(
        ArchiveArtifact.created_at.desc(),
        ArchiveArtifact.id.desc(),
    ).paginate(
        page=normalized_page,
        per_page=normalized_per_page,
        error_out=False,
    )


def count_expired_archives(
    *,
    domain_name: str,
    retention_days: int,
) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=max(retention_days, 1))
    return ArchiveArtifact.query.filter(
        ArchiveArtifact.domain == domain_name,
        ArchiveArtifact.status.in_([ARCHIVE_STATUS_READY, ARCHIVE_STATUS_CLEANUP_PARTIAL]),
        ArchiveArtifact.completed_at.is_not(None),
        ArchiveArtifact.completed_at < cutoff,
    ).count()


def purge_expired_archives(
    *,
    domain_name: str,
    retention_days: int,
    dry_run: bool = False,
) -> dict[str, Any]:
    cutoff = datetime.now(UTC) - timedelta(days=max(retention_days, 1))
    candidates = (
        ArchiveArtifact.query.filter(
            ArchiveArtifact.domain == domain_name,
            ArchiveArtifact.status.in_([ARCHIVE_STATUS_READY, ARCHIVE_STATUS_CLEANUP_PARTIAL]),
            ArchiveArtifact.completed_at.is_not(None),
            ArchiveArtifact.completed_at < cutoff,
        )
        .order_by(ArchiveArtifact.completed_at.asc())
        .all()
    )
    if dry_run:
        return {'matched_count': len(candidates), 'purged_count': 0, 'dry_run': True}

    purged_count = 0
    with retention_lock(f'{domain_name}:archive-purge'):
        for artifact in candidates:
            try:
                if artifact.storage_backend:
                    backend = build_artifact_storage_for_backend(
                        'archive',
                        artifact.storage_backend,
                        locator=_artifact_storage_locator(artifact),
                    )
                    if artifact.data_object_key:
                        backend.delete(artifact.data_object_key)
                    if artifact.manifest_object_key:
                        backend.delete(artifact.manifest_object_key)

                artifact.status = ARCHIVE_STATUS_EXPIRED
                artifact.purged_at = datetime.now(UTC)
                artifact.error_message = None
                db.session.commit()
                purged_count += 1
            except Exception as exc:
                db.session.rollback()
                logger.exception('Could not purge archive %s.', artifact.id)
                failed_artifact = db.session.get(ArchiveArtifact, artifact.id)
                if failed_artifact is not None:
                    failed_artifact.error_message = _error_text(exc)
                    db.session.commit()

    return {'matched_count': len(candidates), 'purged_count': purged_count, 'dry_run': False}


def _execute_archive(
    *,
    artifact_id: str,
    domain,
    policy: RetentionPolicy,
    boundary: ArchiveBoundary,
    cleanup: bool,
) -> dict[str, Any]:
    staging_root = resolve_app_path(
        current_app.config.get('ARCHIVE_STAGING_DIR', 'instance/archive-staging'),
        Path(current_app.instance_path) / 'archive-staging',
    )
    staging_root.mkdir(parents=True, exist_ok=True)
    work_dir = Path(mkdtemp(prefix=f'{domain.name}-', dir=staging_root))
    cleanup_started = False
    deleted_count = 0

    try:
        artifact = _require_archive(artifact_id)
        artifact.status = ARCHIVE_STATUS_ARCHIVING
        db.session.commit()

        file_stem = _build_archive_file_stem(artifact, boundary)
        data_path = work_dir / f'{file_stem}.jsonl.gz'
        manifest_path = work_dir / f'{file_stem}.manifest.json'

        written_count = _write_jsonl_gzip(
            data_path=data_path,
            records=domain.iter_records(boundary, policy),
        )
        if written_count != boundary.record_count:
            raise RuntimeError(
                f'Archive selection changed while writing: expected {boundary.record_count}, wrote {written_count}.'
            )

        checksum = _sha256_file(data_path)
        storage_locator = build_storage_locator('archive')
        backend = build_artifact_storage('archive')
        object_prefix = _build_archive_object_prefix(artifact)
        data_object_key = f'{object_prefix}/{data_path.name}'
        manifest_object_key = f'{object_prefix}/{manifest_path.name}'

        stored_data = backend.save_file(
            data_path,
            data_object_key,
            content_type='application/gzip',
            metadata={
                'sha256': checksum,
                'archive-domain': artifact.domain,
                'schema-version': str(artifact.schema_version),
            },
        )

        artifact.storage_backend = stored_data.backend
        artifact.data_object_key = stored_data.object_key
        artifact.data_uri = stored_data.uri
        artifact.size_bytes = stored_data.size_bytes
        artifact.checksum_sha256 = checksum
        artifact.metadata_json = {
            **(artifact.metadata_json or {}),
            'storage_locator': storage_locator,
        }
        artifact.archived_at = datetime.now(UTC)
        artifact.status = ARCHIVE_STATUS_VERIFYING
        db.session.commit()

        verified_data_path = _verify_stored_file(
            backend=backend,
            object_key=stored_data.object_key,
            expected_size=stored_data.size_bytes,
            expected_checksum=checksum,
        )

        manifest = _build_manifest(
            artifact=artifact,
            boundary=boundary,
            policy=policy,
            cleanup_requested=cleanup,
        )
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + '\n',
            encoding='utf-8',
        )
        manifest_checksum = _sha256_file(manifest_path)
        stored_manifest = backend.save_file(
            manifest_path,
            manifest_object_key,
            content_type='application/json',
            metadata={
                'archive-domain': artifact.domain,
                'archive-id': artifact.id,
                'sha256': manifest_checksum,
            },
        )
        artifact.manifest_object_key = stored_manifest.object_key
        artifact.manifest_uri = stored_manifest.uri
        artifact.manifest_size_bytes = stored_manifest.size_bytes
        artifact.manifest_checksum_sha256 = manifest_checksum
        db.session.commit()

        _verify_stored_file(
            backend=backend,
            object_key=stored_manifest.object_key,
            expected_size=stored_manifest.size_bytes,
            expected_checksum=manifest_checksum,
        )

        artifact.verified_at = datetime.now(UTC)
        db.session.commit()

        if cleanup:
            cleanup_started = True
            artifact.status = ARCHIVE_STATUS_CLEANING
            db.session.commit()
            deleted_count = domain.cleanup_records(
                _iter_archive_record_ids(verified_data_path),
                policy,
            )
            artifact = _require_archive(artifact_id)
            artifact.cleanup_deleted_count = deleted_count
            artifact.cleanup_completed_at = datetime.now(UTC)
            if deleted_count != boundary.record_count:
                artifact.status = ARCHIVE_STATUS_CLEANUP_PARTIAL
                artifact.error_message = (
                    f'Archive contains {boundary.record_count} records, but cleanup removed {deleted_count}. '
                    'The archive remains valid; review concurrent data changes before retrying cleanup.'
                )
            else:
                artifact.status = ARCHIVE_STATUS_READY
                artifact.error_message = None
        else:
            artifact.status = ARCHIVE_STATUS_READY
            artifact.error_message = None

        artifact.completed_at = datetime.now(UTC)
        db.session.commit()

        return {
            'status': artifact.status,
            'archive_id': artifact.id,
            'domain': artifact.domain,
            'record_count': artifact.record_count,
            'cleanup_deleted_count': artifact.cleanup_deleted_count,
            'storage_backend': artifact.storage_backend,
            'data_uri': artifact.data_uri,
            'manifest_uri': artifact.manifest_uri,
            'checksum_sha256': artifact.checksum_sha256,
        }
    except Exception as exc:
        if isinstance(exc, PartialCleanupError):
            deleted_count = exc.deleted_count
            cleanup_started = True
        db.session.rollback()
        logger.exception('Retention archive %s failed.', artifact_id)
        artifact = db.session.get(ArchiveArtifact, artifact_id)
        if artifact is not None:
            artifact.status = (
                ARCHIVE_STATUS_CLEANUP_PARTIAL if cleanup_started and deleted_count > 0 else ARCHIVE_STATUS_FAILED
            )
            artifact.cleanup_deleted_count = deleted_count
            artifact.error_message = _error_text(exc)
            artifact.completed_at = datetime.now(UTC)
            db.session.commit()
        raise
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


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


def _verify_stored_file(
    *,
    backend,
    object_key: str,
    expected_size: int,
    expected_checksum: str,
) -> Path:
    object_stat = backend.stat(object_key)
    if object_stat.size_bytes != expected_size:
        raise ArchiveVerificationError(
            f'Archive size verification failed: expected {expected_size}, found {object_stat.size_bytes}.'
        )

    downloaded_path = backend.build_download_path(object_key)
    actual_checksum = _sha256_file(downloaded_path)
    if actual_checksum != expected_checksum:
        raise ArchiveVerificationError('Archive SHA-256 checksum verification failed.')
    return downloaded_path


def _build_manifest(
    *,
    artifact: ArchiveArtifact,
    boundary: ArchiveBoundary,
    policy: RetentionPolicy,
    cleanup_requested: bool,
) -> dict[str, Any]:
    return {
        'schema_version': 1,
        'archive_id': artifact.id,
        'domain': artifact.domain,
        'source_model': artifact.source_model,
        'generated_at': datetime.now(UTC).isoformat(),
        'trigger_type': artifact.trigger_type,
        'operation_mode': artifact.operation_mode,
        'selection': {
            'cutoff_at': _isoformat(boundary.cutoff_at),
            'maximum_record_id': boundary.maximum_record_id,
            'range_start': _isoformat(boundary.range_start),
            'range_end': _isoformat(boundary.range_end),
            'record_count': boundary.record_count,
            'protected_record_count': boundary.protected_record_count,
            'protected_cutoff_at': _isoformat(boundary.protected_cutoff_at),
        },
        'archive': {
            'format': 'jsonl',
            'compression': 'gzip',
            'content_type': 'application/gzip',
            'size_bytes': artifact.size_bytes,
            'checksum': {
                'algorithm': 'sha256',
                'value': artifact.checksum_sha256,
            },
            'storage_backend': artifact.storage_backend,
            'object_key': artifact.data_object_key,
            'storage_locator': _artifact_storage_locator(artifact),
        },
        'retention_policy': _serialize_policy(policy),
        'cleanup_requested': cleanup_requested,
    }


def _require_archive(archive_id: str) -> ArchiveArtifact:
    artifact = db.session.get(ArchiveArtifact, archive_id)
    if artifact is None:
        raise LookupError('Archive registry row disappeared during processing.')
    return artifact


def _build_archive_file_stem(
    artifact: ArchiveArtifact,
    boundary: ArchiveBoundary,
) -> str:
    range_start = (boundary.range_start or boundary.cutoff_at).strftime('%Y%m%dT%H%M%SZ')
    range_end = (boundary.range_end or boundary.cutoff_at).strftime('%Y%m%dT%H%M%SZ')
    return f'{artifact.domain}-{range_start}-{range_end}-{artifact.id}'


def _build_archive_object_prefix(artifact: ArchiveArtifact) -> str:
    generated_at = (
        artifact.created_at.astimezone(UTC) if artifact.created_at.tzinfo else artifact.created_at.replace(tzinfo=UTC)
    )
    root_prefix = str(current_app.config.get('ARCHIVE_OBJECT_PREFIX', 'archives') or 'archives').strip().strip('/')
    return '/'.join([root_prefix, artifact.domain, generated_at.strftime('%Y'), generated_at.strftime('%m')])


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


def _estimate_uncompressed_size(record_count: int) -> int:
    return max(record_count, 0) * 1200


def _error_text(exc: Exception) -> str:
    message = f'{type(exc).__name__}: {exc}'.strip()
    return message[:4000]
