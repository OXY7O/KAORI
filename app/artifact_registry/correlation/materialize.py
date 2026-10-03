from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import joinedload

from app.artifact_registry.correlation.image_reference import ParsedImageReference, parse_image_reference
from app.common.inventory_generation import filter_current_generation
from app.extensions.db import db
from app.models.inventory import PodInventory
from app.models.registry_artifact import RegistryArtifact, RegistryProject, RegistryRepository
from app.models.registry_correlation import RegistryCorrelationState, RegistryWorkloadBinding

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ArtifactCandidate:
    artifact: RegistryArtifact
    repository_path: str
    registry_hosts: frozenset[str]
    tags: frozenset[str]


@dataclass(frozen=True, slots=True)
class RuntimeImageUsage:
    pod: PodInventory
    container_kind: str
    container_name: str
    image_reference: str
    image_id: str


@dataclass(frozen=True, slots=True)
class MatchResult:
    artifact: RegistryArtifact | None
    match_type: str
    confidence: str
    candidate_count: int
    parsed: ParsedImageReference
    digest_source: str | None


def _state() -> RegistryCorrelationState:
    state = RegistryCorrelationState.query.order_by(RegistryCorrelationState.id.asc()).first()
    if state is None:
        state = RegistryCorrelationState(id=1)
        db.session.add(state)
        db.session.flush()
    return state


def _candidate_rows() -> list[ArtifactCandidate]:
    artifacts = (
        RegistryArtifact.query.options(
            joinedload(RegistryArtifact.tags),
            joinedload(RegistryArtifact.repository)
            .joinedload(RegistryRepository.project)
            .joinedload(RegistryProject.integration_instance),
        )
        .order_by(RegistryArtifact.id.asc())
        .all()
    )
    rows: list[ArtifactCandidate] = []
    for artifact in artifacts:
        repository = artifact.repository
        project = repository.project
        full_path = f'{project.name}/{repository.name}'.strip('/').lower()
        metadata = dict(project.provider_metadata or {})
        hosts = frozenset(str(host).strip().lower() for host in metadata.get('registry_hosts') or () if str(host).strip())
        tags = frozenset(str(tag.name).strip() for tag in artifact.tags if str(tag.name).strip())
        rows.append(
            ArtifactCandidate(
                artifact=artifact,
                repository_path=full_path,
                registry_hosts=hosts,
                tags=tags,
            )
        )
    return rows


def _current_pods() -> list[PodInventory]:
    query = filter_current_generation(
        PodInventory.query.order_by(PodInventory.cluster_id, PodInventory.namespace, PodInventory.pod_name),
        PodInventory,
    )
    return query.all()


def _normalized_runtime_value(value: Any) -> str:
    text = str(value or '').strip()
    return '' if text in {'', '-'} else text


def _runtime_usages(pod: PodInventory) -> list[RuntimeImageUsage]:
    details = dict(pod.details or {})
    rows = details.get('container_statuses')
    usages: list[RuntimeImageUsage] = []
    if isinstance(rows, list) and rows:
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            image = _normalized_runtime_value(row.get('image'))
            if not image:
                continue
            usages.append(
                RuntimeImageUsage(
                    pod=pod,
                    container_kind=_normalized_runtime_value(row.get('kind')) or 'Regular',
                    container_name=_normalized_runtime_value(row.get('name')) or f'container-{index + 1}',
                    image_reference=image,
                    image_id=_normalized_runtime_value(row.get('image_id')),
                )
            )
        if usages:
            return usages

    names = list(pod.container_names or ())
    for index, image in enumerate(pod.container_images or ()):
        image_value = _normalized_runtime_value(image)
        if image_value:
            usages.append(
                RuntimeImageUsage(
                    pod=pod,
                    container_kind='Regular',
                    container_name=str(names[index]) if index < len(names) and names[index] else f'container-{index + 1}',
                    image_reference=image_value,
                    image_id='',
                )
            )
    for index, image in enumerate(pod.init_container_images or ()):
        image_value = _normalized_runtime_value(image)
        if image_value:
            usages.append(
                RuntimeImageUsage(
                    pod=pod,
                    container_kind='Init',
                    container_name=f'init-{index + 1}',
                    image_reference=image_value,
                    image_id='',
                )
            )
    return usages


def _combined_reference(usage: RuntimeImageUsage) -> tuple[ParsedImageReference, str | None]:
    reference = parse_image_reference(usage.image_reference)
    image_id = parse_image_reference(usage.image_id)
    digest = image_id.digest or reference.digest
    digest_source = 'image_id' if image_id.digest else ('image_reference' if reference.digest else None)
    return (
        ParsedImageReference(
            raw=reference.raw,
            registry_host=image_id.registry_host or reference.registry_host,
            repository_path=image_id.repository_path or reference.repository_path,
            tag=reference.tag,
            digest=digest,
        ),
        digest_source,
    )


def _narrow_candidates(
    candidates: list[ArtifactCandidate],
    parsed: ParsedImageReference,
) -> list[ArtifactCandidate]:
    narrowed = candidates
    if parsed.repository_path:
        by_repository = [item for item in narrowed if item.repository_path == parsed.repository_path]
        if not by_repository:
            return []
        narrowed = by_repository
    if parsed.registry_host:
        by_host = [item for item in narrowed if parsed.registry_host in item.registry_hosts]
        if by_host:
            narrowed = by_host
        else:
            return []
    return narrowed


def _match_usage(
    usage: RuntimeImageUsage,
    *,
    digest_index: dict[str, list[ArtifactCandidate]],
    tag_index: dict[tuple[str, str], list[ArtifactCandidate]],
) -> MatchResult:
    parsed, digest_source = _combined_reference(usage)
    if parsed.digest:
        candidates = _narrow_candidates(list(digest_index.get(parsed.digest, ())), parsed)
        if len(candidates) == 1:
            return MatchResult(candidates[0].artifact, 'digest', 'authoritative', 1, parsed, digest_source)
        if len(candidates) > 1:
            return MatchResult(None, 'ambiguous_digest', 'none', len(candidates), parsed, digest_source)
        return MatchResult(None, 'unmatched_digest', 'none', 0, parsed, digest_source)

    if parsed.repository_path and parsed.tag:
        candidates = _narrow_candidates(
            list(tag_index.get((parsed.repository_path, parsed.tag), ())),
            parsed,
        )
        if len(candidates) == 1:
            return MatchResult(candidates[0].artifact, 'tag_reference', 'weak', 1, parsed, None)
        if len(candidates) > 1:
            return MatchResult(None, 'ambiguous_tag', 'none', len(candidates), parsed, None)
        return MatchResult(None, 'unmatched_tag', 'none', 0, parsed, None)

    return MatchResult(None, 'unmatched_reference', 'none', 0, parsed, None)


def _indexes(candidates: list[ArtifactCandidate]) -> tuple[
    dict[str, list[ArtifactCandidate]],
    dict[tuple[str, str], list[ArtifactCandidate]],
]:
    digest_index: dict[str, list[ArtifactCandidate]] = {}
    tag_index: dict[tuple[str, str], list[ArtifactCandidate]] = {}
    for candidate in candidates:
        digest_index.setdefault(candidate.artifact.digest.lower(), []).append(candidate)
        for tag in candidate.tags:
            tag_index.setdefault((candidate.repository_path, tag), []).append(candidate)
    return digest_index, tag_index


def materialize_registry_runtime_correlation() -> dict[str, int | str]:
    """Replace committed Registry↔Kubernetes correlation using committed inventory only."""

    observed_at = datetime.now(UTC)
    state = _state()
    state.last_attempt_at = observed_at
    state.status = 'materializing'
    db.session.flush()

    try:
        candidates = _candidate_rows()
        digest_index, tag_index = _indexes(candidates)
        pods = _current_pods()
        usages = [usage for pod in pods for usage in _runtime_usages(pod)]

        RegistryWorkloadBinding.query.delete(synchronize_session=False)

        digest_matches = tag_matches = ambiguous = unmatched = 0
        for usage in usages:
            match = _match_usage(usage, digest_index=digest_index, tag_index=tag_index)
            artifact = match.artifact
            project = artifact.repository.project if artifact is not None else None
            if match.match_type == 'digest':
                digest_matches += 1
            elif match.match_type == 'tag_reference':
                tag_matches += 1
            elif match.match_type.startswith('ambiguous_'):
                ambiguous += 1
            else:
                unmatched += 1

            binding = RegistryWorkloadBinding(
                registry_artifact_id=artifact.id if artifact is not None else None,
                pod_inventory_id=usage.pod.id,
                cluster_id=usage.pod.cluster_id,
                namespace=usage.pod.namespace,
                pod_name=usage.pod.pod_name,
                workload_type=usage.pod.workload_type,
                workload_name=usage.pod.workload_name,
                container_kind=usage.container_kind,
                container_name=usage.container_name,
                image_reference=usage.image_reference,
                image_id=usage.image_id,
                registry_host=match.parsed.registry_host,
                repository_path=match.parsed.repository_path,
                tag=match.parsed.tag,
                digest=match.parsed.digest,
                match_type=match.match_type,
                confidence=match.confidence,
                candidate_count=match.candidate_count,
                registry_source_id=project.integration_instance_id if project is not None else None,
                registry_provider_key=project.integration_instance.provider_key if project is not None else None,
                registry_observed_at=artifact.observed_at if artifact is not None else None,
                kubernetes_observed_at=usage.pod.collected_at,
                correlated_at=observed_at,
                evidence={
                    'digest_source': match.digest_source,
                    'runtime_image_reference': usage.image_reference,
                    'runtime_image_id': usage.image_id or None,
                    'correlation_boundary': 'committed_registry_and_kubernetes_inventory',
                },
            )
            db.session.add(binding)

        state.status = 'materialized'
        state.last_success_at = observed_at
        state.observed_at = observed_at
        state.last_error = None
        state.runtime_reference_count = len(usages)
        state.digest_match_count = digest_matches
        state.tag_match_count = tag_matches
        state.ambiguous_count = ambiguous
        state.unmatched_count = unmatched
        db.session.commit()
        return {
            'status': state.status,
            'runtime_references': state.runtime_reference_count,
            'digest_matches': state.digest_match_count,
            'tag_matches': state.tag_match_count,
            'ambiguous': state.ambiguous_count,
            'unmatched': state.unmatched_count,
            'observed_at': observed_at.isoformat(),
        }
    except Exception as exc:
        db.session.rollback()
        try:
            state = _state()
            state.status = 'failed'
            state.last_attempt_at = observed_at
            state.last_error = str(exc)[:4000]
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception('Could not persist Registry runtime correlation failure evidence.')
        raise
