from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeprecationRule:
    product: str
    artifact_type: str
    artifact: str
    deprecated_in: str | None
    removed_in: str | None
    replacement: str | None
    behavior: str
    notes: str


RULES: tuple[DeprecationRule, ...] = (
    DeprecationRule(
        product='alertmanager', artifact_type='api', artifact='/api/v1/*',
        deprecated_in='0.16', removed_in='0.27', replacement='/api/v2/*',
        behavior='blocked', notes='KAORI never falls back to Alertmanager API v1.',
    ),
    DeprecationRule(
        product='kubernetes', artifact_type='api', artifact='extensions/v1beta1 Ingress',
        deprecated_in='1.14', removed_in='1.22', replacement='networking.k8s.io/v1 Ingress',
        behavior='blocked', notes='Use the GA Ingress API and pathType field.',
    ),
    DeprecationRule(
        product='kubernetes', artifact_type='api', artifact='batch/v1beta1 CronJob',
        deprecated_in='1.21', removed_in='1.25', replacement='batch/v1 CronJob',
        behavior='blocked', notes='Use batch/v1 for discovery and mutation.',
    ),
    DeprecationRule(
        product='kubernetes', artifact_type='api', artifact='policy/v1beta1 PodDisruptionBudget',
        deprecated_in='1.21', removed_in='1.25', replacement='policy/v1 PodDisruptionBudget',
        behavior='blocked', notes='Selector semantics differ for an empty selector.',
    ),
    DeprecationRule(
        product='kubernetes', artifact_type='api', artifact='policy/v1beta1 PodSecurityPolicy',
        deprecated_in='1.21', removed_in='1.25', replacement=None,
        behavior='blocked', notes='No direct replacement; use Pod Security Admission or a policy engine.',
    ),
    DeprecationRule(
        product='kube-state-metrics', artifact_type='metric',
        artifact='kube_pod_container_resource_requests_cpu_cores',
        deprecated_in='1.9', removed_in='2.0',
        replacement='kube_pod_container_resource_requests{resource="cpu",unit="core"}',
        behavior='replacement_required', notes='Legacy typed metric replaced by resource/unit labels.',
    ),
    DeprecationRule(
        product='kube-state-metrics', artifact_type='metric',
        artifact='kube_pod_container_resource_requests_memory_bytes',
        deprecated_in='1.9', removed_in='2.0',
        replacement='kube_pod_container_resource_requests{resource="memory",unit="byte"}',
        behavior='replacement_required', notes='Legacy typed metric replaced by resource/unit labels.',
    ),
)


def list_deprecations(product: str | None = None) -> tuple[DeprecationRule, ...]:
    if product is None:
        return RULES
    normalized = product.strip().lower()
    return tuple(rule for rule in RULES if rule.product == normalized)
