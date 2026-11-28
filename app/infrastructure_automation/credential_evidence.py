"""Locked current typed credential evidence review (#5184/#5204).

No credential material, grant activation, provider request or execution. The
caller owns the transaction and access scope; the result is not a permit.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import load_only

from app.access.scope_policy import CredentialIssuerScope
from app.extensions.db import db
from app.infrastructure_automation.credential_scope_target import (
    exact_credential_target_current,
    exact_remote_credential_draft_current,
)
from app.integrations.secrets_management.secrets_pki.providers.credential_version_proof import (
    CredentialVersionSelector,
    ProviderCredentialVersionSelector,
)
from app.models.integration import IntegrationInstance
from app.models.scope_access import AutomationCredentialScopeTarget, ScopeAccessPolicy
from app.models.secrets_pki import (
    SecretCredentialIssuerRevision,
    SecretProviderRepresentation,
    SecretVersionObservation,
)
from app.secrets_pki.credential_issuer_resolution import IssuerResolutionTarget, issuer_candidate_key
from app.secrets_pki.issuer_authority import (
    TypedCredentialEvidence,
    resolve_deployment_authority,
    resolve_typed_credential_evidence,
)
from app.secrets_pki.issuer_lifecycle import IssuerLifecycleDenied, require_issuer_source


def resolve_current_credential_evidence(
    policy: ScopeAccessPolicy,
    target: AutomationCredentialScopeTarget,
    *,
    now: datetime,
) -> TypedCredentialEvidence | None:
    """Resolve latest issuer and independently signed exact-version evidence.

    The authenticated service caller must lock the actual policy and target,
    and own rollback. No user-selected issuer, verification key, path or
    proof is accepted. A qualified statement remains offline evidence only.
    """
    if not exact_credential_target_current(policy, target, now=now):
        return None
    return _resolve_qualified_credential_evidence(policy, target, now=now)


def resolve_remote_draft_credential_evidence(
    policy: ScopeAccessPolicy, target: AutomationCredentialScopeTarget, *, now: datetime
) -> TypedCredentialEvidence | None:
    """Review exact disabled remote selector using the same typed provider proof.

    This distinct entry point never widens the active grant evaluator. The
    authenticated caller must qualify the latest draft revision independently.
    """
    if not exact_remote_credential_draft_current(policy, target, now=now):
        return None
    return _resolve_qualified_credential_evidence(policy, target, now=now)


def _resolve_qualified_credential_evidence(
    policy: ScopeAccessPolicy, target: AutomationCredentialScopeTarget, *, now: datetime
) -> TypedCredentialEvidence | None:
    source = db.session.get(
        IntegrationInstance, policy.integration_instance_id, populate_existing=True, with_for_update=True
    )
    representation = db.session.get(
        SecretProviderRepresentation,
        target.secret_representation_id,
        populate_existing=True,
        with_for_update=True,
        options=[
            load_only(
                SecretProviderRepresentation.id,
                SecretProviderRepresentation.secret_identity_id,
                SecretProviderRepresentation.integration_instance_id,
                SecretProviderRepresentation.provider_key,
                SecretProviderRepresentation.provider_namespace,
                SecretProviderRepresentation.mount,
                SecretProviderRepresentation.path_sha256,
                SecretProviderRepresentation.current_version,
            )
        ],
    )
    version = db.session.execute(
        select(SecretVersionObservation)
        .where(
            SecretVersionObservation.representation_id == target.secret_representation_id,
            SecretVersionObservation.version == target.secret_version,
        )
        .with_for_update(of=SecretVersionObservation)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if (
        source is None
        or representation is None
        or version is None
        or source.provider_key not in ('vault', 'openbao')
        or representation.provider_key != source.provider_key
        or representation.integration_instance_id != source.id
        or representation.secret_identity_id != target.secret_identity_id
        or representation.current_version != target.secret_version
        or representation.provider_namespace != policy.provider_namespace
        or representation.mount != policy.mount
        or not isinstance(version.provider_created_time, str)
    ):
        return None

    # Never filter by provider, deployment, active state or requested revision
    # before choosing the latest row: a revoked/newer row blocks old evidence.
    latest = db.session.execute(
        select(SecretCredentialIssuerRevision)
        .where(
            SecretCredentialIssuerRevision.integration_instance_id == source.id,
            SecretCredentialIssuerRevision.provider_namespace == representation.provider_namespace,
            SecretCredentialIssuerRevision.mount == representation.mount,
        )
        .order_by(SecretCredentialIssuerRevision.revision_number.desc())
        .limit(1)
        .with_for_update(of=SecretCredentialIssuerRevision)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if latest is None:
        return None
    issuer_target = IssuerResolutionTarget(
        source.id,
        source.provider_key,
        representation.provider_namespace,
        representation.mount,
        latest.deployment_ref,
        latest.revision_number,
    )
    key = issuer_candidate_key(target=issuer_target, source=source, latest=latest, now=now)
    if key is None:
        return None
    scope = CredentialIssuerScope(
        source.id, source.provider_key, representation.provider_namespace, representation.mount, latest.deployment_ref
    )
    deployment = resolve_deployment_authority(scope, now=now)
    if (
        deployment is None
        or latest.requested_by_user_id != deployment.source_owner_id
        or latest.approved_by_user_id != deployment.checker_id
        or latest.key_sha256 != deployment.transit.key_sha256
    ):
        return None
    try:
        require_issuer_source(scope, deployment)
    except IssuerLifecycleDenied:
        return None
    provider_key = 'vault' if source.provider_key == 'vault' else 'openbao'
    selector = ProviderCredentialVersionSelector(
        provider_key,
        latest.deployment_ref,
        latest.revision_number,
        target.secret_identity_id,
        target.secret_representation_id,
        CredentialVersionSelector(
            source.id,
            representation.provider_namespace,
            representation.mount,
            representation.path_sha256,
            target.secret_version,
            version.provider_created_time,
        ),
    )
    evidence = resolve_typed_credential_evidence(
        selector,
        deployment=deployment,
        issuer_evidence_ref=latest.evidence_ref,
        verification_key=key,
        now=now,
    )
    if (
        evidence is None
        or latest.approved_at is None
        or not latest.approved_at <= evidence.issued_at <= now < evidence.expires_at <= latest.effective_until
    ):
        return None
    return evidence
