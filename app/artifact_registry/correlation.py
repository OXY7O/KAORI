from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import insert
from sqlalchemy.orm import Session, joinedload, selectinload

from app.common.inventory_generation import filter_current_generation
from app.extensions.db import db
from app.models.inventory import PodInventory
from app.models.registry import (
    RegistryArtifact,
    RegistryCollectionState,
    RegistryRepository,
    RegistryWorkloadBinding,
)

CORRELATION_BATCH_SIZE = 250
CorrelationProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True, slots=True)
class ImageReference:
    raw: str
    host: str | None
    repository: str
    tag: str | None
    digest: str | None


def parse_image_reference(value: str) -> ImageReference:
    raw = str(value or '').strip()
    text = raw
    for prefix in ('docker-pullable://', 'docker://', 'containerd://'):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break

    digest = None
    if '@' in text:
        text, digest = text.rsplit('@', 1)
        digest = digest.strip() or None

    tag = None
    last_segment = text.rsplit('/', 1)[-1]
    if ':' in last_segment:
        base, tag = text.rsplit(':', 1)
        text = base
        tag = tag.strip() or None

    segments = text.strip('/').split('/')
    host = None
    repository = text.strip('/')
    if len(segments) > 1 and ('.' in segments[0] or ':' in segments[0] or segments[0] == 'localhost'):
        host = segments[0].lower()
        repository = '/'.join(segments[1:])
    return ImageReference(
        raw=raw,
        host=host,
        repository=repository,
        tag=tag,
        digest=digest,
    )


def _registry_host(session: Session, integration_instance_id: int) -> str | None:
    state = session.get(RegistryCollectionState, int(integration_instance_id))
    if state is None or not isinstance(state.metadata_json, dict):
        return None
    host = str(state.metadata_json.get('registry_host') or '').strip().lower()
    return host or None


def _artifact_repository_path(artifact: RegistryArtifact) -> str:
    return f'{artifact.repository.project.name}/{artifact.repository.name}'.strip('/')


def _match(
    image: ImageReference,
    artifact: RegistryArtifact,
    *,
    registry_host: str | None,
) -> tuple[str, str] | None:
    expected_path = _artifact_repository_path(artifact)
    if image.repository != expected_path:
        return None
    if image.host and registry_host and image.host != registry_host:
        return None
    if image.digest:
        if image.digest == artifact.digest:
            return 'digest', 'strong'
        return None

    tags = {tag.name for tag in artifact.tags}
    if image.tag and image.tag in tags:
        return 'tag', 'medium'
    return None


def _container_rows(pod: PodInventory) -> Iterable[tuple[str, str | None, str]]:
    names = list(pod.container_names or [])
    for index, image in enumerate(pod.container_images or []):
        yield str(image), names[index] if index < len(names) else None, 'container'
    for image in pod.init_container_images or []:
        yield str(image), None, 'init_container'


def refresh_registry_workload_bindings(
    *,
    integration_instance_id: int | None = None,
    progress_callback: CorrelationProgressCallback | None = None,
    batch_size: int = CORRELATION_BATCH_SIZE,
) -> dict[str, int]:
    """Correlate committed Pod images to Registry artifacts in one atomic replacement transaction."""

    normalized_batch_size = max(int(batch_size or CORRELATION_BATCH_SIZE), 1)
    binding_count = digest_matches = tag_matches = 0
    observed_at = datetime.now(UTC)

    # JobExecution progress commits through the application scoped session.
    # Keep correlation replacement state on an independent transaction so
    # heartbeat checkpoints cannot partially commit the materialized binding set.
    with Session(db.engine) as materialization_session, materialization_session.begin():
        artifact_query = materialization_session.query(RegistryArtifact).options(
            joinedload(RegistryArtifact.repository).joinedload(RegistryRepository.project),
            selectinload(RegistryArtifact.tags),
        )
        if integration_instance_id is not None:
            artifact_query = artifact_query.join(
                RegistryRepository,
                RegistryArtifact.repository_id == RegistryRepository.id,
            ).filter(RegistryRepository.project.has(integration_instance_id=integration_instance_id))
        artifacts = artifact_query.all()
        artifact_ids = [artifact.id for artifact in artifacts]

        digest_index: dict[
            tuple[str, str],
            list[tuple[RegistryArtifact, str | None]],
        ] = {}
        tag_index: dict[
            tuple[str, str],
            list[tuple[RegistryArtifact, str | None]],
        ] = {}
        for artifact in artifacts:
            integration_id = artifact.repository.project.integration_instance_id
            registry_host = _registry_host(materialization_session, integration_id)
            repository_path = _artifact_repository_path(artifact)
            digest_index.setdefault(
                (repository_path, artifact.digest),
                [],
            ).append((artifact, registry_host))
            for tag in artifact.tags:
                tag_index.setdefault(
                    (repository_path, tag.name),
                    [],
                ).append((artifact, registry_host))

        pod_query = filter_current_generation(
            materialization_session.query(PodInventory),
            PodInventory,
        ).order_by(PodInventory.id.asc())
        pod_total = pod_query.order_by(None).count()
        if progress_callback is not None:
            progress_callback(0, pod_total, 'Committed Pod Inventory')

        if artifact_ids:
            materialization_session.query(RegistryWorkloadBinding).filter(
                RegistryWorkloadBinding.artifact_id.in_(artifact_ids)
            ).delete(synchronize_session=False)

        pending_bindings: list[dict[str, object]] = []
        for pod_index, pod in enumerate(
            pod_query.yield_per(normalized_batch_size),
            start=1,
        ):
            # RegistryWorkloadBinding identity intentionally collapses duplicate
            # references to the same artifact/image inside one Pod.
            pod_seen: set[tuple[int, str]] = set()
            for raw_image, container_name, source_kind in _container_rows(pod):
                image = parse_image_reference(raw_image)
                candidates = (
                    digest_index.get((image.repository, image.digest), ())
                    if image.digest
                    else (tag_index.get((image.repository, image.tag), ()) if image.tag else ())
                )
                for artifact, registry_host in candidates:
                    match = _match(image, artifact, registry_host=registry_host)
                    if match is None:
                        continue
                    binding_identity = (int(artifact.id), image.raw)
                    if binding_identity in pod_seen:
                        break
                    pod_seen.add(binding_identity)
                    match_type, confidence = match
                    pending_bindings.append(
                        {
                            'artifact_id': artifact.id,
                            'pod_inventory_id': pod.id,
                            'image_reference': image.raw,
                            'match_type': match_type,
                            'confidence': confidence,
                            'cluster_id': str(pod.cluster_id),
                            'namespace': pod.namespace,
                            'workload_type': pod.workload_type,
                            'workload_name': pod.workload_name,
                            'pod_name': pod.pod_name,
                            'container_name': container_name,
                            'details': {
                                'source_kind': source_kind,
                                'registry_observed_at': artifact.observed_at.isoformat(),
                                'pod_collected_at': pod.collected_at.isoformat(),
                                'registry_host': registry_host,
                            },
                            'observed_at': observed_at,
                        }
                    )
                    binding_count += 1
                    digest_matches += int(match_type == 'digest')
                    tag_matches += int(match_type == 'tag')
                    break

            if len(pending_bindings) >= normalized_batch_size:
                materialization_session.execute(
                    insert(RegistryWorkloadBinding),
                    pending_bindings,
                )
                pending_bindings.clear()

            if progress_callback is not None and (pod_index % normalized_batch_size == 0 or pod_index == pod_total):
                progress_callback(
                    pod_index,
                    pod_total,
                    str(pod.pod_name or f'Pod {pod_index}'),
                )

        if pending_bindings:
            materialization_session.execute(
                insert(RegistryWorkloadBinding),
                pending_bindings,
            )

    return {
        'bindings': binding_count,
        'digest_matches': digest_matches,
        'tag_matches': tag_matches,
        'pods_evaluated': pod_total,
    }
