from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.models import AuditEvent
from app.models.tenant import (
    Tenant,
    TenantAccessGrant,
    TenantCapacityDecision,
    TenantCredential,
    TenantNamespace,
)
from app.models.tenant_audit import TenantAuditEvidence
from app.models.tenant_managed_resource import TenantManagedResourceIntent

_ACTIVE_CREDENTIAL = frozenset({'active', 'renewal_due', 'rotating'})
_MUTATING_VERBS = frozenset({'create', 'update', 'patch', 'delete', 'deletecollection'})


def credential_rule_keys(credential, *, owner) -> tuple[str, ...]:
    keys: list[str] = []
    status = str(getattr(credential, 'status', '') or '')
    if status == 'renewal_due':
        keys.append('kubernetes.tenant.credential.renewal_due')

    valid_until = getattr(credential, 'valid_until', None)
    if status in _ACTIVE_CREDENTIAL and isinstance(valid_until, datetime):
        current = datetime.now(UTC)
        effective_until = valid_until if valid_until.tzinfo is not None else valid_until.replace(tzinfo=UTC)
        if effective_until.astimezone(UTC) <= current:
            keys.append('kubernetes.tenant.credential.expired_active')

    reconciliation = str(getattr(credential, 'reconciliation_status', '') or '')
    if reconciliation in {'drifted', 'failed'}:
        keys.append('kubernetes.tenant.credential.reconciliation_drift')

    if not bool(getattr(owner, 'is_active', True)) and status in _ACTIVE_CREDENTIAL:
        keys.append('kubernetes.tenant.credential.inactive_owner_active_access')
    return tuple(keys)


def capacity_rule_key(capacity_state: str, *, decision: str) -> str | None:
    state = str(capacity_state or '').strip()
    mapping = {
        'Near Capacity': 'kubernetes.tenant.capacity.near_capacity',
        'Critical': 'kubernetes.tenant.capacity.near_capacity',
        'Exhausted': 'kubernetes.tenant.capacity.exhausted',
        'Overcommitted': 'kubernetes.tenant.capacity.overcommitted',
        'Unknown': 'kubernetes.tenant.capacity.evidence_unknown',
    }
    if state in mapping:
        return mapping[state]
    if str(decision or '') == 'block':
        return 'kubernetes.tenant.capacity.allocation_denied'
    return None


def provider_rule_key(provider_state: str) -> str | None:
    return {
        'capsule_degraded': 'kubernetes.tenant.provider.degraded',
        'native_recovery': 'kubernetes.tenant.provider.native_recovery',
    }.get(str(provider_state or ''))


def audit_rule_keys(evidence, *, production: bool) -> tuple[str, ...]:
    keys: list[str] = []
    if str(getattr(evidence, 'outcome', '') or '') != 'success':
        return ()

    credential_status = str(getattr(evidence, 'credential_status', '') or '')
    identity_class = str(getattr(evidence, 'identity_class', '') or '')
    correlation_status = str(getattr(evidence, 'correlation_status', '') or '')
    verb = str(getattr(evidence, 'verb', '') or '').lower()
    resource = str(getattr(evidence, 'resource', '') or '').lower()

    if credential_status == 'revoked':
        keys.append('kubernetes.tenant.credential.revoked_still_usable')
    if correlation_status in {'unmanaged', 'ambiguous'}:
        keys.append('kubernetes.tenant.access.unmanaged_principal')
    if resource == 'clusterrolebindings' and correlation_status == 'matched':
        keys.append('kubernetes.tenant.access.cluster_scope_binding')
    if production and verb in _MUTATING_VERBS and identity_class in {'human', 'admin', 'group'}:
        keys.append('kubernetes.tenant.production.human_mutation')
    if production and verb in _MUTATING_VERBS and resource in {'deployments', 'statefulsets', 'daemonsets', 'jobs', 'cronjobs'}:
        if identity_class != 'cicd':
            keys.append('kubernetes.tenant.production.deployment_outside_cicd')
    return tuple(keys)


def _finding(
    rule: dict[str, Any] | None,
    *,
    suffix: str,
    title: str,
    summary: str,
    evidence: dict[str, Any],
) -> dict[str, Any] | None:
    if not rule:
        return None
    finding = dict(rule)
    finding.update(
        {
            'rule_key': f"{rule['rule_key']}:{suffix}",
            'title': title,
            'summary': summary,
            'condition_summary': summary,
            'status': 'available',
            'evidence': evidence,
        }
    )
    return finding


def _append(
    findings: list[dict[str, Any]],
    rules: dict[str, dict[str, Any]],
    rule_key: str,
    *,
    suffix: str,
    title: str,
    summary: str,
    evidence: dict[str, Any],
) -> None:
    finding = _finding(rules.get(rule_key), suffix=suffix, title=title, summary=summary, evidence=evidence)
    if finding is not None:
        findings.append(finding)


def _credential_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for credential in TenantCredential.query.all():
        owner = credential.owner_user
        for rule_key in credential_rule_keys(credential, owner=owner):
            evidence = {
                'asset_key': credential.tenant.cluster_id,
                'cluster_id': credential.tenant.cluster_id,
                'tenant_id': credential.tenant_id,
                'credential_id': credential.public_id,
                'credential_type': credential.credential_type,
                'credential_status': credential.status,
                'owner_user_id': credential.owner_user_id,
                'reconciliation_status': credential.reconciliation_status,
                'renewal_due_at': credential.renewal_due_at.isoformat(),
                'valid_until': credential.valid_until.isoformat(),
                'affected_count': 1,
            }
            _append(
                findings,
                rules,
                rule_key,
                suffix=credential.public_id,
                title=f'Tenant credential {credential.purpose} requires governance review',
                summary=f'Committed credential state reports {rule_key.rsplit(".", 1)[-1].replace("_", " ")}.',
                evidence=evidence,
            )
    return findings


def _access_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for grant in TenantAccessGrant.query.all():
        evidence = {
            'asset_key': grant.tenant.cluster_id,
            'cluster_id': grant.tenant.cluster_id,
            'tenant_id': grant.tenant_id,
            'grant_id': grant.public_id,
            'scope_type': grant.scope_type,
            'access_profile': grant.access_profile,
            'grant_status': grant.status,
            'membership_status': grant.membership.status,
            'reconciliation_status': grant.reconciliation_status,
            'affected_count': 1,
        }
        if grant.reconciliation_status in {'drifted', 'failed'}:
            _append(
                findings,
                rules,
                'kubernetes.tenant.access.grant_drift',
                suffix=grant.public_id,
                title=f'Access Grant {grant.public_id} differs from committed intent',
                summary='Committed Access Grant reconciliation is drifted or failed.',
                evidence=evidence,
            )
        if grant.status == 'active' and grant.membership.status != 'active':
            _append(
                findings,
                rules,
                'kubernetes.tenant.access.grant_without_active_membership',
                suffix=grant.public_id,
                title='Active Access Grant has no active membership',
                summary='The Access Grant remains active while its canonical membership is not active.',
                evidence=evidence,
            )
    return findings


def _namespace_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for namespace in TenantNamespace.query.all():
        evidence = {
            'asset_key': namespace.cluster_id,
            'cluster_id': namespace.cluster_id,
            'tenant_id': namespace.environment.tenant_id,
            'environment': namespace.environment.environment,
            'namespace': namespace.namespace,
            'ownership_status': namespace.ownership_status,
            'provisioning_status': namespace.provisioning_status,
            'resource_profile_version': namespace.resource_profile_version,
            'affected_count': 1,
        }
        if namespace.ownership_status == 'discovered':
            _append(
                findings,
                rules,
                'kubernetes.tenant.namespace.unmanaged',
                suffix=f'{namespace.cluster_id}:{namespace.namespace}',
                title=f'Namespace {namespace.namespace} is discovered but not governed',
                summary='Namespace ownership is discovered rather than managed or adopted.',
                evidence=evidence,
            )
        profile_mismatch = (
            namespace.provisioning_status in {'drifted', 'failed'}
            or (
                namespace.desired_hash is not None
                and namespace.effective_hash is not None
                and namespace.desired_hash != namespace.effective_hash
            )
        )
        if profile_mismatch:
            _append(
                findings,
                rules,
                'kubernetes.tenant.namespace.profile_drift',
                suffix=f'{namespace.cluster_id}:{namespace.namespace}',
                title=f'Namespace {namespace.namespace} has Resource Profile drift',
                summary='Committed namespace provisioning evidence differs from effective provider state.',
                evidence=evidence,
            )

    for tenant in Tenant.query.all():
        has_admin = any(
            grant.status == 'active'
            and grant.access_profile == 'tenant_admin'
            and grant.membership.status == 'active'
            for grant in tenant.access_grants
        )
        if not has_admin:
            _append(
                findings,
                rules,
                'kubernetes.tenant.namespace.missing_tenant_admin',
                suffix=tenant.id,
                title=f'Tenant {tenant.name} has no active Tenant Admin',
                summary='No active Tenant Admin Access Grant is committed for this Tenant.',
                evidence={
                    'asset_key': tenant.cluster_id,
                    'cluster_id': tenant.cluster_id,
                    'tenant_id': tenant.id,
                    'tenant_name': tenant.name,
                    'affected_count': 1,
                },
            )
    return findings


def _managed_resource_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for intent in TenantManagedResourceIntent.query.filter(
        TenantManagedResourceIntent.status.in_(['drifted', 'failed'])
    ).all():
        _append(
            findings,
            rules,
            'kubernetes.tenant.policy.managed_resource_drift',
            suffix=intent.public_id,
            title=f'Managed {intent.resource_kind} resource {intent.resource_name} is not reconciled',
            summary='Platform-security managed resource evidence is drifted or failed.',
            evidence={
                'asset_key': intent.tenant.cluster_id,
                'cluster_id': intent.tenant.cluster_id,
                'tenant_id': intent.tenant_id,
                'namespace': intent.namespace.namespace,
                'resource_kind': intent.resource_kind,
                'resource_name': intent.resource_name,
                'mode': intent.mode,
                'status': intent.status,
                'affected_count': 1,
            },
        )
    return findings


def _provider_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for tenant in Tenant.query.all():
        rule_key = provider_rule_key(tenant.provider_state)
        if rule_key is None:
            continue
        _append(
            findings,
            rules,
            rule_key,
            suffix=tenant.id,
            title=f'Tenant {tenant.name} provider state is {tenant.provider_state.replace("_", " ")}',
            summary='Committed provider capability/authority evidence requires operator review.',
            evidence={
                'asset_key': tenant.cluster_id,
                'cluster_id': tenant.cluster_id,
                'tenant_id': tenant.id,
                'tenant_name': tenant.name,
                'provider_key': tenant.provider_key,
                'provider_state': tenant.provider_state,
                'reconciliation_authority': tenant.reconciliation_authority,
                'provider_evidence_json': tenant.provider_evidence_json or {},
                'affected_count': 1,
            },
        )
    return findings


def _capacity_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    rows = TenantCapacityDecision.query.order_by(TenantCapacityDecision.id.desc()).all()
    for decision in rows:
        identity = (decision.cluster_id, decision.namespace)
        if identity in seen:
            continue
        seen.add(identity)
        rule_key = capacity_rule_key(decision.capacity_state, decision=decision.decision)
        if rule_key is None:
            continue
        _append(
            findings,
            rules,
            rule_key,
            suffix=f'{decision.cluster_id}:{decision.namespace}',
            title=f'Tenant allocation posture for {decision.namespace}: {decision.capacity_state}',
            summary='Latest committed Tenant Allocation decision requires capacity governance review.',
            evidence={
                'asset_key': decision.cluster_id,
                'cluster_id': decision.cluster_id,
                'namespace': decision.namespace,
                'decision': decision.decision,
                'capacity_state': decision.capacity_state,
                'operation': decision.operation,
                'resource_profile_version': decision.resource_profile_version,
                'data_cutoff': decision.data_cutoff.isoformat() if decision.data_cutoff else None,
                'capacity_evidence': decision.evidence_json or {},
                'affected_count': 1,
            },
        )
    return findings


def _audit_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str | None]] = set()
    rows = TenantAuditEvidence.query.order_by(TenantAuditEvidence.event_at.desc()).limit(500).all()
    for evidence in rows:
        namespace = evidence.namespace
        production = bool(namespace and namespace.environment.environment == 'production')
        for rule_key in audit_rule_keys(evidence, production=production):
            dedupe = (rule_key, evidence.principal_username, evidence.kubernetes_namespace)
            if dedupe in seen:
                continue
            seen.add(dedupe)
            _append(
                findings,
                rules,
                rule_key,
                suffix=evidence.public_id,
                title=f'Tenant runtime governance finding for {evidence.principal_username}',
                summary=f'Normalized Kubernetes audit evidence matched {rule_key.rsplit(".", 1)[-1].replace("_", " ")}.',
                evidence={
                    'asset_key': evidence.cluster_id,
                    'cluster_id': evidence.cluster_id,
                    'tenant_id': evidence.tenant_id,
                    'namespace': evidence.kubernetes_namespace,
                    'principal_username': evidence.principal_username,
                    'identity_class': evidence.identity_class,
                    'correlation_status': evidence.correlation_status,
                    'credential_status': evidence.credential_status,
                    'verb': evidence.verb,
                    'resource': evidence.resource,
                    'resource_name': evidence.resource_name,
                    'event_at': evidence.event_at.isoformat(),
                    'source_reference': evidence.source_reference,
                    'production': production,
                    'affected_count': 1,
                },
            )
    return findings


def _policy_event_findings(rules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    events = (
        AuditEvent.query.filter(
            AuditEvent.action.in_(
                [
                    'tenant.exposure_policy.service_preflight',
                    'tenant.exposure_policy.ingress_preflight',
                    'tenant.production_access_decision',
                ]
            )
        )
        .order_by(AuditEvent.id.desc())
        .limit(300)
        .all()
    )
    seen: set[tuple[str, str | None]] = set()
    for event in events:
        metadata = event.metadata_json or {}
        rule_key = None
        if event.action.startswith('tenant.exposure_policy.') and metadata.get('allowed') is False:
            rule_key = 'kubernetes.tenant.policy.exposure_violation'
        elif event.action == 'tenant.production_access_decision':
            findings_value = metadata.get('findings')
            values = set(findings_value if isinstance(findings_value, list) else [])
            if 'production_human_mutation' in values:
                rule_key = 'kubernetes.tenant.production.human_mutation'
        if rule_key is None:
            continue
        dedupe = (rule_key, event.target_id)
        if dedupe in seen:
            continue
        seen.add(dedupe)
        _append(
            findings,
            rules,
            rule_key,
            suffix=str(event.id),
            title='Tenant policy decision requires operator review',
            summary=event.summary,
            evidence={
                'tenant_id': metadata.get('tenant_id'),
                'namespace': metadata.get('namespace'),
                'allowed': metadata.get('allowed'),
                'authority': metadata.get('authority'),
                'findings': metadata.get('findings') or [],
                'event_action': event.action,
                'event_at': event.created_at.isoformat(),
                'affected_count': 1,
            },
        )
    return findings


def build_tenant_governance_recommendation_findings(
    rules: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Evaluate Tenant Governance only from committed KAORI evidence."""

    try:
        return [
            *_credential_findings(rules),
            *_access_findings(rules),
            *_namespace_findings(rules),
            *_managed_resource_findings(rules),
            *_provider_findings(rules),
            *_capacity_findings(rules),
            *_audit_findings(rules),
            *_policy_event_findings(rules),
        ]
    except SQLAlchemyError:
        return []
