from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from types import MappingProxyType
from typing import Any, Protocol

from app.integrations.kubernetes.client import KubernetesClient
from app.integrations.kubernetes.resolver import resolve_kubernetes_for_cluster
from app.resolver.contracts import (
    DryRunResult,
    ResolverContext,
    ResolverError,
    ResolverResult,
    ResolverResultStatus,
    VerificationResult,
    VerificationStatus,
)

ACTION_KEY = 'kubernetes.deployment.restart'
CAPABILITY_KEY = 'kubernetes.deployments.patch'
COMPATIBILITY_PROFILE = 'kubernetes-v1'
RESTART_ANNOTATION = 'kaori.io/restarted-at'
MANAGED_ANNOTATION = 'kaori.io/managed-remediation'


class KubernetesMutationGateway(Protocol):
    def can_patch_deployments(self, namespace: str) -> bool: ...

    def read_deployment(self, namespace: str, name: str) -> Mapping[str, Any]: ...

    def patch_deployment(
        self,
        namespace: str,
        name: str,
        patch: Mapping[str, Any],
        *,
        dry_run: bool,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class NamespaceGuardrail:
    allowed_namespaces: frozenset[str]
    denied_namespaces: frozenset[str] = frozenset({'kube-system', 'kube-public', 'kube-node-lease'})

    def assert_allowed(self, namespace: str) -> None:
        if namespace in self.denied_namespaces:
            raise ResolverError(f'Namespace is protected from remediation: {namespace}.')
        if self.allowed_namespaces and namespace not in self.allowed_namespaces:
            raise ResolverError(f'Namespace is outside the remediation allowlist: {namespace}.')


class KubernetesApiMutationGateway:
    """Canonical Kubernetes API gateway used by mutation adapters."""

    def __init__(self, cluster_id: str) -> None:
        runtime = resolve_kubernetes_for_cluster(cluster_id)
        if runtime is None:
            raise ResolverError(f'No canonical Kubernetes runtime is available for cluster: {cluster_id}.')
        self._client = KubernetesClient(
            runtime.connection.kubeconfig,
            verify_ssl=bool(runtime.connection.verify_ssl),
        )

    def can_patch_deployments(self, namespace: str) -> bool:
        body = {
            'apiVersion': 'authorization.k8s.io/v1',
            'kind': 'SelfSubjectAccessReview',
            'spec': {
                'resourceAttributes': {
                    'group': 'apps',
                    'resource': 'deployments',
                    'verb': 'patch',
                    'namespace': namespace,
                }
            },
        }
        response = self._client.authorization_api().create_self_subject_access_review(body=body)
        return bool(getattr(getattr(response, 'status', None), 'allowed', False))

    def read_deployment(self, namespace: str, name: str) -> Mapping[str, Any]:
        deployment = self._client.apps_api().read_namespaced_deployment(name=name, namespace=namespace)
        metadata = getattr(deployment, 'metadata', None)
        spec = getattr(deployment, 'spec', None)
        status = getattr(deployment, 'status', None)
        annotations = dict(getattr(metadata, 'annotations', None) or {})
        conditions = [
            {
                'type': str(getattr(condition, 'type', '') or ''),
                'status': str(getattr(condition, 'status', '') or ''),
                'reason': str(getattr(condition, 'reason', '') or ''),
                'message': str(getattr(condition, 'message', '') or ''),
            }
            for condition in (getattr(status, 'conditions', None) or [])
        ]
        return MappingProxyType(
            {
                'name': name,
                'namespace': namespace,
                'uid': str(getattr(metadata, 'uid', '') or ''),
                'resource_version': str(getattr(metadata, 'resource_version', '') or ''),
                'generation': int(getattr(metadata, 'generation', 0) or 0),
                'observed_generation': int(getattr(status, 'observed_generation', 0) or 0),
                'desired_replicas': int(getattr(spec, 'replicas', 1) or 0),
                'updated_replicas': int(getattr(status, 'updated_replicas', 0) or 0),
                'ready_replicas': int(getattr(status, 'ready_replicas', 0) or 0),
                'available_replicas': int(getattr(status, 'available_replicas', 0) or 0),
                'unavailable_replicas': int(getattr(status, 'unavailable_replicas', 0) or 0),
                'conditions': conditions,
                'annotations': annotations,
            }
        )

    def patch_deployment(
        self,
        namespace: str,
        name: str,
        patch: Mapping[str, Any],
        *,
        dry_run: bool,
    ) -> Mapping[str, Any]:
        response = self._client.apps_api().patch_namespaced_deployment(
            name=name,
            namespace=namespace,
            body=dict(patch),
            dry_run='All' if dry_run else None,
            field_manager='kaori-resolver',
        )
        metadata = getattr(response, 'metadata', None)
        return MappingProxyType(
            {
                'uid': str(getattr(metadata, 'uid', '') or ''),
                'resource_version': str(getattr(metadata, 'resource_version', '') or ''),
                'generation': int(getattr(metadata, 'generation', 0) or 0),
                'annotations': dict(getattr(metadata, 'annotations', None) or {}),
            }
        )


class KubernetesDeploymentRestartAdapter:
    action_key = ACTION_KEY
    capability_keys = (CAPABILITY_KEY,)
    compatibility_profiles = (COMPATIBILITY_PROFILE,)
    rollback_required = False

    def __init__(
        self,
        *,
        gateway_factory: Callable[[str], KubernetesMutationGateway] = KubernetesApiMutationGateway,
        namespace_guardrail: NamespaceGuardrail | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._gateway_factory = gateway_factory
        self._guardrail = namespace_guardrail or NamespaceGuardrail(frozenset())
        self._clock = clock or (lambda: datetime.now(UTC))

    def dry_run(self, context: ResolverContext) -> DryRunResult:
        cluster_id, namespace, deployment_name = self._target(context)
        self._guardrail.assert_allowed(namespace)
        gateway = self._gateway_factory(cluster_id)
        if not gateway.can_patch_deployments(namespace):
            return DryRunResult(False, 'Kubernetes service account cannot patch deployments in the namespace.')

        current = dict(gateway.read_deployment(namespace, deployment_name))
        resource_version = str(current.get('resource_version') or '')
        uid = str(current.get('uid') or '')
        if not resource_version or not uid:
            return DryRunResult(False, 'Deployment identity or resourceVersion is unavailable.')

        expected_resource_version = str(context.parameters.get('resource_version') or '')
        if expected_resource_version and expected_resource_version != resource_version:
            return DryRunResult(False, 'Deployment resourceVersion changed before dry-run.')

        timestamp = self._clock().isoformat()
        previous_annotation = dict(current.get('annotations') or {}).get(RESTART_ANNOTATION)
        patch = self._restart_patch(resource_version, timestamp)
        dry_response = dict(gateway.patch_deployment(namespace, deployment_name, patch, dry_run=True))
        if str(dry_response.get('uid') or uid) != uid:
            return DryRunResult(False, 'Kubernetes dry-run returned a different deployment identity.')

        snapshot = {
            'cluster_id': cluster_id,
            'namespace': namespace,
            'name': deployment_name,
            'uid': uid,
            'resource_version': resource_version,
            'generation': _safe_int(current.get('generation')),
            'previous_restart_annotation': previous_annotation,
        }
        rollback = {
            'mode': 'manual_compensating_recovery',
            'automatic': False,
            'target': {'cluster_id': cluster_id, 'namespace': namespace, 'name': deployment_name, 'uid': uid},
            'previous_restart_annotation': previous_annotation,
            'snapshot_hash': _snapshot_hash(snapshot),
            'guidance': (
                'Deployment restart is not transactionally reversible. Use the pre-change snapshot and workload '
                'health evidence for accountable compensating recovery or escalation.'
            ),
        }
        return DryRunResult(
            True,
            f'Deployment restart dry-run accepted for {namespace}/{deployment_name}.',
            planned_changes=(
                MappingProxyType(
                    {
                        'operation': 'patch',
                        'resource': 'apps/v1/deployments',
                        'target': f'{namespace}/{deployment_name}',
                        'precondition_resource_version': resource_version,
                        'patch': patch,
                        'pre_change_snapshot': snapshot,
                    }
                ),
            ),
            rollback_plan=MappingProxyType(rollback),
        )

    def execute(self, context: ResolverContext, dry_run: DryRunResult) -> ResolverResult:
        if not dry_run.allowed or not dry_run.planned_changes:
            raise ResolverError('Kubernetes execution requires an accepted dry-run plan.')
        cluster_id, namespace, deployment_name = self._target(context)
        self._guardrail.assert_allowed(namespace)
        gateway = self._gateway_factory(cluster_id)
        if not gateway.can_patch_deployments(namespace):
            raise ResolverError('Kubernetes service account lost deployment patch permission.')

        plan = dict(dry_run.planned_changes[0])
        snapshot = dict(plan.get('pre_change_snapshot') or {})
        current = dict(gateway.read_deployment(namespace, deployment_name))
        if str(current.get('uid') or '') != str(snapshot.get('uid') or ''):
            raise ResolverError('Deployment identity changed after dry-run.')
        if str(current.get('resource_version') or '') != str(snapshot.get('resource_version') or ''):
            raise ResolverError('Deployment resourceVersion changed after dry-run.')

        result = dict(gateway.patch_deployment(namespace, deployment_name, plan['patch'], dry_run=False))
        expected_annotation = plan['patch']['spec']['template']['metadata']['annotations'][RESTART_ANNOTATION]
        verified = dict(gateway.read_deployment(namespace, deployment_name))
        actual_annotation = dict(verified.get('annotations') or {}).get(RESTART_ANNOTATION)
        if actual_annotation != expected_annotation:
            return ResolverResult(
                ResolverResultStatus.FAILED,
                'Deployment patch completed but the restart annotation could not be verified.',
                result={'target': f'{namespace}/{deployment_name}'},
                rollback_reference=_rollback_reference(dry_run.rollback_plan),
                retryable=True,
            )

        return ResolverResult(
            ResolverResultStatus.SUCCEEDED,
            f'Deployment restart annotation applied to {namespace}/{deployment_name}.',
            result={
                'target': f'{namespace}/{deployment_name}',
                'uid': result.get('uid') or verified.get('uid'),
                'resource_version': result.get('resource_version') or verified.get('resource_version'),
                'generation': result.get('generation') or verified.get('generation'),
                'post_condition': 'restart annotation verified',
            },
            rollback_reference=_rollback_reference(dry_run.rollback_plan),
            retryable=False,
        )

    def verify(self, context: ResolverContext, result: ResolverResult) -> VerificationResult:
        if result.status not in {ResolverResultStatus.SUCCEEDED, ResolverResultStatus.NOOP}:
            return VerificationResult(
                VerificationStatus.FAILED,
                'Execution did not succeed, so remediation verification cannot pass.',
            )
        cluster_id, namespace, deployment_name = self._target(context)
        self._guardrail.assert_allowed(namespace)
        deployment = dict(self._gateway_factory(cluster_id).read_deployment(namespace, deployment_name))
        expected_uid = str(result.result.get('uid') or '')
        actual_uid = str(deployment.get('uid') or '')
        if expected_uid and actual_uid != expected_uid:
            return VerificationResult(
                VerificationStatus.FAILED,
                'Deployment identity changed after the authorized restart.',
                evidence=deployment,
            )

        target_generation = _safe_int(result.result.get('generation'))
        observed_generation = _safe_int(deployment.get('observed_generation'))
        desired = _safe_int(deployment.get('desired_replicas'), default=1)
        updated = _safe_int(deployment.get('updated_replicas'))
        ready = _safe_int(deployment.get('ready_replicas'))
        available = _safe_int(deployment.get('available_replicas'))
        unavailable = _safe_int(deployment.get('unavailable_replicas'))
        evidence = {
            'target': f'{namespace}/{deployment_name}',
            'uid': actual_uid,
            'target_generation': target_generation,
            'observed_generation': observed_generation,
            'desired_replicas': desired,
            'updated_replicas': updated,
            'ready_replicas': ready,
            'available_replicas': available,
            'unavailable_replicas': unavailable,
            'conditions': list(deployment.get('conditions') or []),
        }
        for condition in evidence['conditions']:
            if (
                str(condition.get('type') or '') == 'Progressing'
                and str(condition.get('status') or '').lower() == 'false'
                and str(condition.get('reason') or '') == 'ProgressDeadlineExceeded'
            ):
                return VerificationResult(
                    VerificationStatus.FAILED,
                    'Deployment rollout exceeded its progress deadline after restart.',
                    evidence=evidence,
                )

        generation_observed = target_generation <= 0 or observed_generation >= target_generation
        replicas_healthy = updated >= desired and ready >= desired and available >= desired and unavailable == 0
        if generation_observed and replicas_healthy:
            return VerificationResult(
                VerificationStatus.VERIFIED,
                f'Deployment rollout verified healthy for {namespace}/{deployment_name}.',
                evidence=evidence,
            )
        return VerificationResult(
            VerificationStatus.PENDING,
            f'Deployment rollout is still converging for {namespace}/{deployment_name}.',
            evidence=evidence,
        )

    def _target(self, context: ResolverContext) -> tuple[str, str, str]:
        if context.action_key != ACTION_KEY:
            raise ResolverError(f'Unsupported Kubernetes resolver action: {context.action_key}.')
        cluster_id = str(context.cluster_id or '').strip()
        namespace = str(context.namespace or '').strip()
        deployment_name = str(context.parameters.get('deployment_name') or '').strip()
        if not cluster_id or not namespace or not deployment_name:
            raise ResolverError('Kubernetes deployment restart requires cluster, namespace, and deployment_name.')
        return cluster_id, namespace, deployment_name

    @staticmethod
    def _restart_patch(resource_version: str, timestamp: str) -> dict[str, Any]:
        return {
            'metadata': {'resourceVersion': resource_version},
            'spec': {
                'template': {
                    'metadata': {
                        'annotations': {
                            RESTART_ANNOTATION: timestamp,
                            MANAGED_ANNOTATION: 'true',
                        }
                    }
                }
            },
        }


def _snapshot_hash(snapshot: Mapping[str, Any]) -> str:
    payload = json.dumps(dict(snapshot), sort_keys=True, separators=(',', ':'), default=str)
    return sha256(payload.encode('utf-8')).hexdigest()


def _rollback_reference(plan: Mapping[str, Any] | None) -> str | None:
    if not plan:
        return None
    return f'kubernetes-snapshot:{plan.get("snapshot_hash")}'


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default
