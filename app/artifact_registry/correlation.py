from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from urllib.parse import urlsplit

from sqlalchemy import insert, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.common.inventory_generation import filter_current_generation
from app.extensions.db import db
from app.models.inventory import ClusterInventory, PodInventory
from app.models.integration import IntegrationInstance
from app.models.job import JobExecution
from app.models.registry import (
    RegistryArtifact,
    RegistryCollectionState,
    RegistryProject,
    RegistryRepository,
    RegistryWorkloadBinding,
)

CORRELATION_BATCH_SIZE = 250


def _active_registry_source_ids(session: Session) -> list[int]:
    return [
        int(source_id)
        for (source_id,) in session.query(IntegrationInstance.id).filter(
            IntegrationInstance.integration_type == 'registry',
            IntegrationInstance.lifecycle_status == 'active',
            IntegrationInstance.enabled.is_(True),
        ).all()
    ]


def runtime_input_signature(session: Session) -> str:
    """Fingerprint committed Registry and Kubernetes generation authorities.

    No provider calls and no full artifact or Pod inventory traversal.
    """
    source_ids = _active_registry_source_ids(session)
    registry_rows = session.query(
        RegistryCollectionState.integration_instance_id,
        RegistryCollectionState.last_committed_at,
    ).filter(RegistryCollectionState.integration_instance_id.in_(source_ids)).all()
    pod_generations = session.query(
        ClusterInventory.cluster_id, ClusterInventory.collected_at
    ).all()
    evidence = {
        'active_registry_sources': sorted(source_ids),
        'registry': sorted(
            (int(source_id), committed_at.isoformat() if committed_at else None)
            for source_id, committed_at in registry_rows
        ),
        'kubernetes': sorted(
            (str(cluster_id), collected_at.isoformat() if collected_at else None)
            for cluster_id, collected_at in pod_generations
        ),
    }
    return sha256(json.dumps(evidence, sort_keys=True).encode('utf-8')).hexdigest()


def runtime_correlation_evidence_readiness(session: Session) -> dict[str, str]:
    """Qualify committed runtime evidence without live provider I/O."""
    jobs = session.query(JobExecution).filter(
        JobExecution.job_type == 'artifact_registry_runtime_correlation'
    )
    latest = jobs.order_by(JobExecution.created_at.desc(), JobExecution.id.desc()).first()
    successful = jobs.filter(
        JobExecution.status.in_(('succeeded', 'partially_succeeded'))
    ).order_by(JobExecution.completed_at.desc(), JobExecution.id.desc()).first()

    if successful is None:
        return {
            'status': 'not_materialized',
            'title': 'Runtime Correlation Required',
            'description': (
                'No successful committed Registry-to-Kubernetes correlation exists. '
                'Run the registered Runtime Correlation job before interpreting absent findings.'
            ),
        }

    summary = successful.result_summary_json if isinstance(successful.result_summary_json, dict) else {}
    committed_signature = summary.get('input_signature')
    if not committed_signature or committed_signature != runtime_input_signature(session):
        return {
            'status': 'inputs_changed',
            'title': 'Runtime Correlation Inputs Changed',
            'description': (
                'Committed Registry or Kubernetes inventory changed after the last correlation. '
                'Stored scan vulnerabilities are not remediated merely because runtime findings disappear. '
                'Refresh Runtime Correlation to requalify exposure.'
            ),
        }

    if latest is not None and latest.is_active:
        return {
            'status': 'refreshing',
            'title': 'Runtime Correlation Refreshing',
            'description': 'A registered correlation job is in progress; the prior committed snapshot remains provisional.',
        }
    if latest is not None and latest.status == 'failed' and latest.created_at > successful.created_at:
        return {
            'status': 'refresh_failed',
            'title': 'Runtime Correlation Refresh Failed',
            'description': 'The latest refresh failed; review Job Executions before treating an absent binding as resolved.',
        }
    observed_at = successful.completed_at or successful.created_at
    if observed_at is None or observed_at < datetime.now(UTC) - timedelta(hours=24):
        return {
            'status': 'stale',
            'title': 'Runtime Correlation Evidence Stale',
            'description': 'The last successful correlation is over 24 hours old. Refresh before relying on runtime exposure.',
        }
    return {
        'status': 'ready',
        'title': 'Runtime Correlation Ready',
        'description': 'Current committed Registry and Kubernetes input generations match the last successful correlation.',
    }


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


def _normalized_registry_host(value: str | None) -> str | None:
    """Compare explicit Registry authority including non-default ports."""
    if not value:
        return None
    try:
        parsed = urlsplit(f'//{value.strip().lower()}')
        hostname = (parsed.hostname or '').rstrip('.')
        port = parsed.port
    except ValueError:
        return None
    if not hostname:
        return None
    authority = f'[{hostname}]' if ':' in hostname else hostname
    return f'{authority}:{port}' if port not in (None, 443) else authority


def _match(
    image: ImageReference,
    artifact: RegistryArtifact,
    *,
    registry_host: str | None,
) -> tuple[str, str] | None:
    expected_path = _artifact_repository_path(artifact)
    if image.repository != expected_path:
        return None
    # Unknown or implicit hosts are not proof of source identity. A digest
    # alone must never attribute a runtime image to an unrelated Registry.
    expected_host = _normalized_registry_host(registry_host)
    observed_host = _normalized_registry_host(image.host)
    if expected_host is None or observed_host is None or observed_host != expected_host:
        return None
    if image.digest:
        if image.digest == artifact.digest:
            return 'digest', 'strong'
        return None

    tags = {tag.name for tag in artifact.tags}
    if image.tag and image.tag in tags:
        return 'tag', 'medium'
    return None


@dataclass(frozen=True, slots=True)
class IndexedArtifact:
    id: int
    repository: str
    digest: str
    tag: str | None
    host: str | None
    observed_at: datetime


def _match_indexed(image: ImageReference, candidate: IndexedArtifact) -> tuple[str, str] | None:
    if image.repository != candidate.repository:
        return None
    expected_host = _normalized_registry_host(candidate.host)
    if not expected_host or _normalized_registry_host(image.host) != expected_host:
        return None
    if image.digest:
        return ('digest', 'strong') if image.digest == candidate.digest else None
    return ('tag', 'medium') if image.tag and image.tag == candidate.tag else None


def _container_rows(pod: PodInventory) -> Iterable[tuple[str, str, str, int]]:
    names = list(pod.container_names or [])
    for index, image in enumerate(pod.container_images or []):
        name = str(names[index]) if index < len(names) and names[index] else f'Container {index + 1}'
        yield str(image), name, 'container', index
    for index, image in enumerate(pod.init_container_images or []):
        # PodInventory does not persist init-container names; retain their
        # stable position instead of pretending that their names are known.
        yield str(image), f'Init container {index + 1}', 'init_container', index


def refresh_registry_workload_bindings(
    *,
    integration_instance_id: int | None = None,
    progress_callback: CorrelationProgressCallback | None = None,
    batch_size: int = CORRELATION_BATCH_SIZE,
) -> dict[str, int | str]:
    """Correlate committed Pod images to Registry artifacts in one atomic replacement transaction."""

    normalized_batch_size = max(int(batch_size or CORRELATION_BATCH_SIZE), 1)
    binding_count = digest_matches = tag_matches = 0
    observed_at = datetime.now(UTC)

    # JobExecution progress commits through the application scoped session.
    # Keep correlation replacement state on an independent transaction so
    # heartbeat checkpoints cannot partially commit the materialized binding set.
    with Session(db.engine) as materialization_session, materialization_session.begin():
        input_signature = runtime_input_signature(materialization_session)
        active_source_ids = _active_registry_source_ids(materialization_session)
        target_source_ids = (
            [source_id for source_id in active_source_ids if source_id == int(integration_instance_id)]
            if integration_instance_id is not None
            else active_source_ids
        )
        artifact_query = materialization_session.query(RegistryArtifact).filter(
            RegistryArtifact.repository.has(
                RegistryRepository.project.has(
                    RegistryProject.integration_instance_id.in_(target_source_ids)
                )
            )
        ).options(
            joinedload(RegistryArtifact.repository).joinedload(RegistryRepository.project),
            selectinload(RegistryArtifact.tags),
        )
        digest_index: dict[tuple[str, str], list[IndexedArtifact]] = {}
        tag_index: dict[tuple[str, str], list[IndexedArtifact]] = {}
        host_by_source: dict[int, str | None] = {}
        for artifact in artifact_query.yield_per(normalized_batch_size):
            integration_id = int(artifact.repository.project.integration_instance_id)
            if integration_id not in host_by_source:
                host_by_source[integration_id] = _registry_host(materialization_session, integration_id)
            registry_host = host_by_source[integration_id]
            repository_path = _artifact_repository_path(artifact)
            candidate = IndexedArtifact(
                id=int(artifact.id),
                repository=repository_path,
                digest=artifact.digest,
                tag=None,
                host=registry_host,
                observed_at=artifact.observed_at,
            )
            digest_index.setdefault((repository_path, artifact.digest), []).append(candidate)
            for tag in artifact.tags:
                tag_index.setdefault((repository_path, tag.name), []).append(
                    IndexedArtifact(
                        id=candidate.id,
                        repository=repository_path,
                        digest=candidate.digest,
                        tag=tag.name,
                        host=registry_host,
                        observed_at=candidate.observed_at,
                    )
                )

        pod_query = filter_current_generation(
            materialization_session.query(PodInventory),
            PodInventory,
        ).order_by(PodInventory.id.asc())
        pod_total = pod_query.order_by(None).count()
        if progress_callback is not None:
            progress_callback(0, pod_total, 'Committed Pod Inventory')

        artifact_id_scope = (
            select(RegistryArtifact.id)
            .join(RegistryRepository, RegistryArtifact.repository_id == RegistryRepository.id)
            .join(RegistryProject, RegistryRepository.project_id == RegistryProject.id)
            .where(RegistryProject.integration_instance_id.in_(target_source_ids))
        )
        materialization_session.query(RegistryWorkloadBinding).filter(
            RegistryWorkloadBinding.artifact_id.in_(artifact_id_scope)
        ).delete(synchronize_session=False)

        pending_bindings: list[dict[str, object]] = []
        for pod_index, pod in enumerate(
            pod_query.yield_per(normalized_batch_size),
            start=1,
        ):
            # Preserve each matching container inside the canonical unique
            # artifact/Pod/image binding, without changing the DB constraint.
            pod_bindings: dict[tuple[int, str], dict[str, object]] = {}
            pod_usages: dict[tuple[int, str], list[dict[str, str | int]]] = {}
            for raw_image, container_name, source_kind, container_index in _container_rows(pod):
                image = parse_image_reference(raw_image)
                candidates = (
                    digest_index.get((image.repository, image.digest), ())
                    if image.digest
                    else (tag_index.get((image.repository, image.tag), ()) if image.tag else ())
                )
                resolved = [
                    (candidate, match)
                    for candidate in candidates
                    if (match := _match_indexed(image, candidate)) is not None
                ]
                # Two Registry instances claiming the same image authority
                # cannot be distinguished from committed image evidence.
                if len(resolved) != 1:
                    continue
                candidate, match = resolved[0]
                binding_identity = (candidate.id, image.raw)
                usage = {
                    'name': container_name,
                    'source_kind': source_kind,
                    'index': container_index,
                }
                existing_usages = pod_usages.get(binding_identity)
                if existing_usages is not None:
                    existing_usages.append(usage)
                    continue
                pod_usages[binding_identity] = [usage]
                match_type, confidence = match
                binding: dict[str, object] = {
                    'artifact_id': candidate.id,
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
                        'containers': pod_usages[binding_identity],
                        'registry_observed_at': candidate.observed_at.isoformat(),
                        'pod_collected_at': pod.collected_at.isoformat(),
                        'registry_host': candidate.host,
                    },
                    'observed_at': observed_at,
                }
                pod_bindings[binding_identity] = binding
                binding_count += 1
                digest_matches += int(match_type == 'digest')
                tag_matches += int(match_type == 'tag')
            pending_bindings.extend(pod_bindings.values())

            if len(pending_bindings) >= normalized_batch_size:
                materialization_session.execute(
                    insert(RegistryWorkloadBinding),
                    pending_bindings,
                )
                pending_bindings.clear()

            if progress_callback is not None and (
                pod_index % normalized_batch_size == 0 or pod_index == pod_total
            ):
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
        if runtime_input_signature(materialization_session) != input_signature:
            raise RuntimeError(
                'Committed Registry or Kubernetes inventory generation changed during runtime correlation.'
            )

    return {
        'bindings': binding_count,
        'digest_matches': digest_matches,
        'tag_matches': tag_matches,
        'pods_evaluated': pod_total,
        'input_signature': input_signature,
    }
