from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

from sqlalchemy.orm import joinedload

from app.common.inventory_generation import filter_current_generation
from app.extensions.db import db
from app.models.inventory import PodInventory
from app.models.registry import (
    RegistryArtifact,
    RegistryCollectionState,
    RegistryRepository,
    RegistryWorkloadBinding,
)


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
            text = text[len(prefix):]
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


def _registry_host(integration_instance_id: int) -> str | None:
    state = db.session.get(RegistryCollectionState, int(integration_instance_id))
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
) -> dict[str, int]:
    """Correlate committed Pod image references to committed Registry artifact identity."""

    query = RegistryArtifact.query.options(
        joinedload(RegistryArtifact.repository).joinedload(RegistryRepository.project),
        joinedload(RegistryArtifact.tags),
    )
    if integration_instance_id is not None:
        query = query.join(
            RegistryRepository,
            RegistryArtifact.repository_id == RegistryRepository.id,
        ).filter(
            RegistryRepository.project.has(
                integration_instance_id=integration_instance_id
            )
        )
    artifacts = query.all()
    artifact_ids = [artifact.id for artifact in artifacts]
    if artifact_ids:
        RegistryWorkloadBinding.query.filter(
            RegistryWorkloadBinding.artifact_id.in_(artifact_ids)
        ).delete(synchronize_session=False)
    db.session.flush()

    by_path: dict[str, list[tuple[RegistryArtifact, str | None]]] = {}
    for artifact in artifacts:
        integration_id = artifact.repository.project.integration_instance_id
        registry_host = _registry_host(integration_id)
        by_path.setdefault(_artifact_repository_path(artifact), []).append(
            (artifact, registry_host)
        )

    binding_count = digest_matches = tag_matches = 0
    observed_at = datetime.now(UTC)
    pods = filter_current_generation(PodInventory.query, PodInventory).order_by(PodInventory.id.asc()).all()
    for pod in pods:
        for raw_image, container_name, source_kind in _container_rows(pod):
            image = parse_image_reference(raw_image)
            for artifact, registry_host in by_path.get(image.repository, ()):
                match = _match(image, artifact, registry_host=registry_host)
                if match is None:
                    continue
                match_type, confidence = match
                db.session.add(
                    RegistryWorkloadBinding(
                        artifact_id=artifact.id,
                        pod_inventory_id=pod.id,
                        image_reference=image.raw,
                        match_type=match_type,
                        confidence=confidence,
                        cluster_id=str(pod.cluster_id),
                        namespace=pod.namespace,
                        workload_type=pod.workload_type,
                        workload_name=pod.workload_name,
                        pod_name=pod.pod_name,
                        container_name=container_name,
                        details={
                            'source_kind': source_kind,
                            'registry_observed_at': artifact.observed_at.isoformat(),
                            'pod_collected_at': pod.collected_at.isoformat(),
                            'registry_host': registry_host,
                        },
                        observed_at=observed_at,
                    )
                )
                binding_count += 1
                digest_matches += int(match_type == 'digest')
                tag_matches += int(match_type == 'tag')
                break

    db.session.commit()
    return {
        'bindings': binding_count,
        'digest_matches': digest_matches,
        'tag_matches': tag_matches,
    }
