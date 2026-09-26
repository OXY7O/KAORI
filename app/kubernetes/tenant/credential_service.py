from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import yaml
from kubernetes.client import V1TokenRequest, V1TokenRequestSpec
from kubernetes.client.rest import ApiException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.extensions.db import db
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.adapter import runtime_adapter
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.resolver import connection_for_cluster
from app.kubernetes.tenant.credential import (
    DEFAULT_CREDENTIAL_VALIDITY_DAYS,
    DEFAULT_RENEWAL_WINDOW_DAYS,
    DEFAULT_TOKEN_TTL_SECONDS,
    build_namespace_access_package,
    credential_target_namespaces,
    effective_credential_status,
    normalize_credential_purpose,
    refresh_credential_status,
    token_ttl_seconds,
    validate_credential_contract,
)
from app.kubernetes.tenant.credential_reconciliation import (
    reconcile_native_credential,
    remove_native_credential_access,
)
from app.models import AuditEvent, Cluster, User
from app.models.tenant import (
    Tenant,
    TenantAccessGrant,
    TenantAccessReconciliationStatus,
    TenantCredential,
    TenantCredentialDeliveryMethod,
    TenantCredentialGeneration,
    TenantCredentialStatus,
    TenantCredentialType,
    TenantNamespace,
)

_MAX_VALIDITY_DAYS = 3650


class TenantCredentialStateConflictError(RuntimeError):
    """Committed Tenant credential state changed while a mutation was applying."""


@dataclass(frozen=True, slots=True)
class GeneratedTokenMaterial:
    credential_public_id: str
    namespace: str
    service_account_name: str
    expires_at: datetime
    access_package: dict[str, object]
    token: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class GeneratedKubeconfigMaterial:
    credential_public_id: str
    namespace: str
    expires_at: datetime
    access_package: dict[str, object]
    kubeconfig: str = field(repr=False)


def _now() -> datetime:
    return datetime.now(UTC)


def _validity_window(
    *,
    validity_days: int,
    now: datetime | None = None,
) -> tuple[datetime, datetime, datetime]:
    days = int(validity_days)
    if days < 1 or days > _MAX_VALIDITY_DAYS:
        raise ValueError(f'Tenant credential validity must be between 1 and {_MAX_VALIDITY_DAYS} days.')
    started = now or _now()
    valid_until = started + timedelta(days=days)
    renewal_window_days = min(DEFAULT_RENEWAL_WINDOW_DAYS, max(days - 1, 0))
    renewal_due_at = valid_until - timedelta(days=renewal_window_days)
    return started, renewal_due_at, valid_until


def _service_account_name(public_id: str, *, admin: bool) -> str:
    prefix = 'kaori-admin' if admin else 'kaori-human'
    return f'{prefix}-{public_id.replace("-", "")[:12]}'


def _record_event(
    *,
    actor: User | None,
    credential: TenantCredential,
    action: str,
    summary: str,
    outcome: str,
    extra: dict[str, object] | None = None,
) -> None:
    event = AuditEvent()
    event.actor_user_id = actor.id if actor is not None else None
    event.target_type = 'tenant_credential'
    event.target_id = credential.public_id
    event.action = action
    event.summary = summary
    event.metadata_json = {
        'tenant_id': credential.tenant_id,
        'owner_user_id': credential.owner_user_id,
        'credential_type': credential.credential_type,
        'delivery_method': credential.delivery_method,
        'purpose': credential.purpose,
        'credential_status': credential.status,
        'reconciliation_status': credential.reconciliation_status,
        'rotation_generation': credential.rotation_generation,
        'valid_until': credential.valid_until.isoformat(),
        'outcome': outcome,
        'correlation_id': credential.correlation_id,
        'secret_material_persisted': False,
        **(extra or {}),
    }
    db.session.add(event)


def _record_generation(credential: TenantCredential, *, issued_at: datetime) -> TenantCredentialGeneration:
    generation = TenantCredentialGeneration()
    generation.credential = credential
    generation.generation = credential.rotation_generation
    generation.issued_at = issued_at
    generation.provider_evidence_json = {
        'reconciliation_status': credential.reconciliation_status,
        'desired_hash': credential.desired_hash,
        'effective_hash': credential.effective_hash,
        'targets': list((credential.reconciliation_evidence_json or {}).get('effective_targets') or []),
        'secret_material_persisted': False,
    }
    db.session.add(generation)
    return generation


def _existing_owner_purpose(
    *,
    tenant_id: str,
    owner_user_id: int,
    credential_type: str,
    purpose: str,
) -> TenantCredential | None:
    return TenantCredential.query.filter_by(
        tenant_id=tenant_id,
        owner_user_id=owner_user_id,
        credential_type=credential_type,
        purpose=purpose,
    ).first()


def create_human_credential_committed(
    *,
    access_grant_id: int,
    owner_user_id: int,
    jumpserver_reference: str,
    purpose: str = 'interactive',
    validity_days: int = DEFAULT_CREDENTIAL_VALIDITY_DAYS,
    delivery_method: str = TenantCredentialDeliveryMethod.JUMPSERVER.value,
    exception_authorized_by_user_id: int | None = None,
    exception_reason: str | None = None,
    exception_valid_until: datetime | None = None,
    actor: User | None = None,
) -> TenantCredential:
    grant = db.session.get(TenantAccessGrant, access_grant_id)
    owner = db.session.get(User, owner_user_id)
    if grant is None:
        raise ValueError('Select an active Tenant Access Grant.')
    if owner is None or not owner.is_active:
        raise ValueError('Select an active credential owner.')
    if grant.reconciliation_status != TenantAccessReconciliationStatus.READY.value:
        raise ValueError('Reconcile the Tenant Access Grant before issuing a human credential.')

    normalized_purpose = normalize_credential_purpose(purpose)
    if (
        _existing_owner_purpose(
            tenant_id=grant.tenant_id,
            owner_user_id=owner.id,
            credential_type=TenantCredentialType.HUMAN_SERVICE_ACCOUNT.value,
            purpose=normalized_purpose,
        )
        is not None
    ):
        raise ValueError('This user already has a Tenant human credential for the selected purpose.')

    method = TenantCredentialDeliveryMethod(delivery_method)
    if method not in {
        TenantCredentialDeliveryMethod.JUMPSERVER,
        TenantCredentialDeliveryMethod.EXCEPTIONAL_KUBECONFIG,
    }:
        raise ValueError('Human Tenant credentials require JumpServer or governed exceptional kubeconfig delivery.')

    approver = (
        db.session.get(User, exception_authorized_by_user_id)
        if exception_authorized_by_user_id is not None
        else None
    )
    started, renewal_due_at, valid_until = _validity_window(validity_days=validity_days)
    public_id = str(uuid.uuid4())

    credential = TenantCredential()
    credential.public_id = public_id
    credential.tenant_id = grant.tenant_id
    credential.owner_user = owner
    credential.access_grant = grant
    credential.credential_type = TenantCredentialType.HUMAN_SERVICE_ACCOUNT.value
    credential.purpose = normalized_purpose
    credential.delivery_method = method.value
    credential.status = TenantCredentialStatus.ACTIVE.value
    credential.service_account_name = _service_account_name(public_id, admin=False)
    credential.jumpserver_reference = jumpserver_reference.strip()
    credential.exception_authorized_by = approver
    credential.exception_reason = (exception_reason or '').strip() or None
    credential.exception_valid_until = exception_valid_until
    credential.valid_from = started
    credential.renewal_due_at = renewal_due_at
    credential.valid_until = valid_until
    credential.rotation_generation = 1
    db.session.add(credential)

    try:
        validate_credential_contract(credential)
        db.session.flush()
        reconcile_native_credential(credential)
        _record_generation(credential, issued_at=started)
        _record_event(
            actor=actor,
            credential=credential,
            action='tenant_credential.issued',
            summary='Tenant human credential entitlement was issued and reconciled.',
            outcome='success',
            extra={'access_grant_id': grant.public_id},
        )
        db.session.commit()
        return credential
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantCredentialStateConflictError(
            'Committed Tenant credential state changed while this credential was being issued. Refresh and retry.'
        ) from exc
    except (ApiException, ValueError):
        db.session.rollback()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise


def create_admin_credential_committed(
    *,
    tenant_id: str,
    owner_user_id: int,
    anchor_namespace_id: int,
    purpose: str = 'administrative',
    validity_days: int = DEFAULT_CREDENTIAL_VALIDITY_DAYS,
    actor: User | None = None,
) -> TenantCredential:
    tenant = db.session.get(Tenant, tenant_id)
    owner = db.session.get(User, owner_user_id)
    namespace = db.session.get(TenantNamespace, anchor_namespace_id)
    if tenant is None:
        raise ValueError('Select a Tenant.')
    if owner is None or not owner.is_active or not owner.is_admin_level:
        raise ValueError('Administrative kubeconfig ownership requires an active KAORI administrator.')
    if namespace is None:
        raise ValueError('Select a Ready managed namespace as the administrative credential anchor.')

    normalized_purpose = normalize_credential_purpose(purpose)
    if (
        _existing_owner_purpose(
            tenant_id=tenant.id,
            owner_user_id=owner.id,
            credential_type=TenantCredentialType.ADMIN_KUBECONFIG.value,
            purpose=normalized_purpose,
        )
        is not None
    ):
        raise ValueError('This administrator already has a Tenant administrative credential for the selected purpose.')

    started, renewal_due_at, valid_until = _validity_window(validity_days=validity_days)
    public_id = str(uuid.uuid4())
    credential = TenantCredential()
    credential.public_id = public_id
    credential.tenant = tenant
    credential.owner_user = owner
    credential.anchor_namespace = namespace
    credential.credential_type = TenantCredentialType.ADMIN_KUBECONFIG.value
    credential.purpose = normalized_purpose
    credential.delivery_method = TenantCredentialDeliveryMethod.ADMIN_KUBECONFIG.value
    credential.status = TenantCredentialStatus.ACTIVE.value
    credential.service_account_name = _service_account_name(public_id, admin=True)
    credential.valid_from = started
    credential.renewal_due_at = renewal_due_at
    credential.valid_until = valid_until
    credential.rotation_generation = 1
    db.session.add(credential)

    try:
        validate_credential_contract(credential)
        db.session.flush()
        reconcile_native_credential(credential)
        _record_generation(credential, issued_at=started)
        _record_event(
            actor=actor,
            credential=credential,
            action='tenant_credential.admin_issued',
            summary='Individual administrative Tenant kubeconfig entitlement was issued and reconciled.',
            outcome='success',
            extra={'anchor_namespace_id': namespace.id},
        )
        db.session.commit()
        return credential
    except IntegrityError as exc:
        db.session.rollback()
        raise TenantCredentialStateConflictError(
            'Committed Tenant credential state changed while this admin credential was being issued. Refresh and retry.'
        ) from exc
    except (ApiException, ValueError):
        db.session.rollback()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise


def _retire_current_generation(credential: TenantCredential, *, retired_at: datetime) -> None:
    current = (
        TenantCredentialGeneration.query.filter_by(
            credential_id=credential.id,
            generation=credential.rotation_generation,
        ).first()
    )
    if current is not None and current.retired_at is None:
        current.retired_at = retired_at


def renew_credential_committed(
    *,
    credential_id: int,
    validity_days: int = DEFAULT_CREDENTIAL_VALIDITY_DAYS,
    actor: User | None = None,
) -> TenantCredential:
    credential = db.session.get(TenantCredential, credential_id)
    if credential is None:
        raise ValueError('Selected Tenant credential no longer exists.')
    if credential.status == TenantCredentialStatus.REVOKED.value:
        raise ValueError('Revoked Tenant credentials cannot be renewed.')

    now = _now()
    started, renewal_due_at, valid_until = _validity_window(validity_days=validity_days, now=now)
    try:
        credential.status = TenantCredentialStatus.ROTATING.value
        remove_native_credential_access(credential)
        _retire_current_generation(credential, retired_at=now)

        credential.rotation_generation += 1
        credential.valid_from = started
        credential.renewal_due_at = renewal_due_at
        credential.valid_until = valid_until
        credential.status = TenantCredentialStatus.ACTIVE.value
        reconcile_native_credential(credential)
        _record_generation(credential, issued_at=now)
        _record_event(
            actor=actor,
            credential=credential,
            action='tenant_credential.renewed',
            summary='Tenant credential was rotated to a new independently traceable generation.',
            outcome='success',
        )
        db.session.commit()
        return credential
    except (ApiException, ValueError):
        credential.status = TenantCredentialStatus.ROTATING.value
        _record_event(
            actor=actor,
            credential=credential,
            action='tenant_credential.renew_failed',
            summary='Tenant credential rotation requires operator attention.',
            outcome='failed',
        )
        db.session.commit()
        raise
    except SQLAlchemyError:
        db.session.rollback()
        raise


def suspend_credential_committed(*, credential_id: int, actor: User | None = None) -> TenantCredential:
    credential = db.session.get(TenantCredential, credential_id)
    if credential is None:
        raise ValueError('Selected Tenant credential no longer exists.')
    if credential.status == TenantCredentialStatus.REVOKED.value:
        raise ValueError('Revoked Tenant credentials cannot be suspended.')

    credential.status = TenantCredentialStatus.SUSPENDED.value
    try:
        reconcile_native_credential(credential)
        _record_event(
            actor=actor,
            credential=credential,
            action='tenant_credential.suspended',
            summary='Tenant credential was suspended and effective Kubernetes access was removed.',
            outcome='success',
        )
        db.session.commit()
        return credential
    except (ApiException, ValueError):
        _record_event(
            actor=actor,
            credential=credential,
            action='tenant_credential.suspend_failed',
            summary='Tenant credential is suspended in KAORI but provider removal requires attention.',
            outcome='failed',
        )
        db.session.commit()
        raise


def resume_credential_committed(*, credential_id: int, actor: User | None = None) -> TenantCredential:
    credential = db.session.get(TenantCredential, credential_id)
    if credential is None:
        raise ValueError('Selected Tenant credential no longer exists.')
    if credential.status != TenantCredentialStatus.SUSPENDED.value:
        raise ValueError('Only a suspended Tenant credential can be resumed.')

    credential.status = TenantCredentialStatus.ACTIVE.value
    next_status = effective_credential_status(credential, now=_now())
    if next_status == TenantCredentialStatus.EXPIRED.value:
        credential.status = TenantCredentialStatus.EXPIRED.value
        reconcile_native_credential(credential)
        db.session.commit()
        raise ValueError('Expired Tenant credential must be renewed instead of resumed.')

    credential.status = next_status
    try:
        reconcile_native_credential(credential)
        _record_event(
            actor=actor,
            credential=credential,
            action='tenant_credential.resumed',
            summary='Tenant credential was resumed and effective Kubernetes access was reconciled.',
            outcome='success',
        )
        db.session.commit()
        return credential
    except (ApiException, ValueError):
        _record_event(
            actor=actor,
            credential=credential,
            action='tenant_credential.resume_failed',
            summary='Tenant credential resume requires operator attention.',
            outcome='failed',
        )
        db.session.commit()
        raise


def revoke_credential_committed(*, credential_id: int, actor: User | None = None) -> TenantCredential:
    credential = db.session.get(TenantCredential, credential_id)
    if credential is None:
        raise ValueError('Selected Tenant credential no longer exists.')
    if credential.status == TenantCredentialStatus.REVOKED.value:
        return credential

    credential.status = TenantCredentialStatus.REVOKED.value
    try:
        reconcile_native_credential(credential)
        _retire_current_generation(credential, retired_at=_now())
        _record_event(
            actor=actor,
            credential=credential,
            action='tenant_credential.revoked',
            summary='Tenant credential was revoked and effective Kubernetes access was removed.',
            outcome='success',
        )
        db.session.commit()
        return credential
    except (ApiException, ValueError):
        _record_event(
            actor=actor,
            credential=credential,
            action='tenant_credential.revoke_failed',
            summary='Tenant credential is revoked in KAORI but provider removal requires attention.',
            outcome='failed',
        )
        db.session.commit()
        raise


def enforce_credential_lifecycle_committed(
    *,
    credential_id: int,
    actor: User | None = None,
) -> TenantCredential:
    credential = db.session.get(TenantCredential, credential_id)
    if credential is None:
        raise ValueError('Selected Tenant credential no longer exists.')

    before = credential.status
    refresh_credential_status(credential)
    if credential.status == TenantCredentialStatus.EXPIRED.value:
        reconcile_native_credential(credential)
        if before != credential.status:
            _record_event(
                actor=actor,
                credential=credential,
                action='tenant_credential.expired',
                summary='Tenant credential expired and effective Kubernetes access was removed.',
                outcome='success',
            )
    elif credential.status == TenantCredentialStatus.RENEWAL_DUE.value and before != credential.status:
        _record_event(
            actor=actor,
            credential=credential,
            action='tenant_credential.renewal_due',
            summary='Tenant credential entered its governed renewal window.',
            outcome='success',
        )
    db.session.commit()
    return credential


def _target_namespace(credential: TenantCredential, namespace_id: int) -> TenantNamespace:
    namespace = db.session.get(TenantNamespace, namespace_id)
    if namespace is None:
        raise ValueError('Selected Tenant namespace no longer exists.')
    allowed = {item.id for item in credential_target_namespaces(credential)}
    if namespace.id not in allowed:
        raise ValueError('Selected namespace is outside this Tenant credential scope.')
    return namespace


def _request_short_lived_token(
    credential: TenantCredential,
    namespace: TenantNamespace,
    *,
    requested_seconds: int,
) -> tuple[str, datetime]:
    refresh_credential_status(credential)
    if credential.status == TenantCredentialStatus.EXPIRED.value:
        reconcile_native_credential(credential)
        raise ValueError('Tenant credential is expired.')
    validate_credential_contract(credential)
    reconcile_native_credential(credential)

    ttl = token_ttl_seconds(credential, requested_seconds=requested_seconds)
    cluster = db.session.get(Cluster, credential.tenant.cluster_id)
    if cluster is None:
        raise ValueError('Tenant cluster no longer exists.')
    api = runtime_adapter.build_client(cluster).core_api()
    response = api.create_namespaced_service_account_token(
        name=credential.service_account_name,
        namespace=namespace.namespace,
        body=V1TokenRequest(
            api_version='authentication.k8s.io/v1',
            kind='TokenRequest',
            spec=V1TokenRequestSpec(audiences=[], expiration_seconds=ttl),
        ),
    )
    status = getattr(response, 'status', None)
    token = str(getattr(status, 'token', '') or '')
    expires_at = getattr(status, 'expiration_timestamp', None)
    if not token or expires_at is None:
        raise ValueError('Kubernetes did not return short-lived ServiceAccount credential material.')
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return token, expires_at.astimezone(UTC)


def issue_jumpserver_token_committed(
    *,
    credential_id: int,
    namespace_id: int,
    requested_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
    actor: User | None = None,
) -> GeneratedTokenMaterial:
    credential = db.session.get(TenantCredential, credential_id)
    if credential is None:
        raise ValueError('Selected Tenant credential no longer exists.')
    if credential.credential_type != TenantCredentialType.HUMAN_SERVICE_ACCOUNT.value:
        raise ValueError('JumpServer token delivery is available only for human Tenant credentials.')
    if credential.delivery_method not in {
        TenantCredentialDeliveryMethod.JUMPSERVER.value,
        TenantCredentialDeliveryMethod.EXCEPTIONAL_KUBECONFIG.value,
    }:
        raise ValueError('This Tenant credential is not approved for JumpServer delivery.')

    namespace = _target_namespace(credential, namespace_id)
    token, expires_at = _request_short_lived_token(
        credential,
        namespace,
        requested_seconds=requested_seconds,
    )
    package = build_namespace_access_package(credential, namespace).as_dict()
    _record_event(
        actor=actor,
        credential=credential,
        action='tenant_credential.jumpserver_material_issued',
        summary='Short-lived Tenant credential material was issued for JumpServer delivery.',
        outcome='success',
        extra={'namespace': namespace.namespace, 'expires_at': expires_at.isoformat()},
    )
    db.session.commit()
    return GeneratedTokenMaterial(
        credential_public_id=credential.public_id,
        namespace=namespace.namespace,
        service_account_name=credential.service_account_name,
        expires_at=expires_at,
        access_package=package,
        token=token,
    )


def _transport_config(cluster: Cluster) -> dict[str, object]:
    connection = connection_for_cluster(cluster)
    document = yaml.safe_load(connection.kubeconfig) or {}
    current_context = str(document.get('current-context') or '')
    contexts = {
        str(item.get('name')): item.get('context') or {}
        for item in document.get('contexts') or []
        if isinstance(item, dict)
    }
    selected_cluster = str((contexts.get(current_context) or {}).get('cluster') or '')
    clusters = {
        str(item.get('name')): item.get('cluster') or {}
        for item in document.get('clusters') or []
        if isinstance(item, dict)
    }
    cluster_config = clusters.get(selected_cluster) or next(iter(clusters.values()), {})
    server = str(connection.server or cluster_config.get('server') or '').strip()
    if not server:
        raise ValueError('Canonical Kubernetes connection has no API server endpoint.')

    result: dict[str, object] = {'server': server}
    ca_data = str(cluster_config.get('certificate-authority-data') or '').strip()
    if ca_data:
        result['certificate-authority-data'] = ca_data
    elif not connection.verify_ssl:
        result['insecure-skip-tls-verify'] = True
    return result


def generate_kubeconfig_committed(
    *,
    credential_id: int,
    namespace_id: int,
    requested_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
    actor: User | None = None,
) -> GeneratedKubeconfigMaterial:
    credential = db.session.get(TenantCredential, credential_id)
    if credential is None:
        raise ValueError('Selected Tenant credential no longer exists.')

    if credential.credential_type == TenantCredentialType.HUMAN_SERVICE_ACCOUNT.value:
        if credential.delivery_method != TenantCredentialDeliveryMethod.EXCEPTIONAL_KUBECONFIG.value:
            raise ValueError('Ordinary-user kubeconfig generation requires explicit governed exception approval.')
        if credential.exception_valid_until is None:
            raise ValueError('Exceptional ordinary-user kubeconfig approval requires an expiry.')
    elif credential.delivery_method != TenantCredentialDeliveryMethod.ADMIN_KUBECONFIG.value:
        raise ValueError('Administrative credential is not approved for kubeconfig generation.')

    namespace = _target_namespace(credential, namespace_id)
    token, expires_at = _request_short_lived_token(
        credential,
        namespace,
        requested_seconds=requested_seconds,
    )
    cluster = db.session.get(Cluster, credential.tenant.cluster_id)
    if cluster is None:
        raise ValueError('Tenant cluster no longer exists.')

    context_name = f'kaori-{credential.public_id[:8]}'
    transport = _transport_config(cluster)
    document = {
        'apiVersion': 'v1',
        'kind': 'Config',
        'clusters': [{'name': cluster.name, 'cluster': transport}],
        'contexts': [
            {
                'name': context_name,
                'context': {
                    'cluster': cluster.name,
                    'namespace': namespace.namespace,
                    'user': credential.service_account_name,
                },
            }
        ],
        'current-context': context_name,
        'users': [
            {
                'name': credential.service_account_name,
                'user': {'token': token},
            }
        ],
    }
    rendered = yaml.safe_dump(document, sort_keys=False)
    package = build_namespace_access_package(credential, namespace).as_dict()
    action = (
        'tenant_credential.exceptional_kubeconfig_generated'
        if credential.credential_type == TenantCredentialType.HUMAN_SERVICE_ACCOUNT.value
        else 'tenant_credential.admin_kubeconfig_generated'
    )
    _record_event(
        actor=actor,
        credential=credential,
        action=action,
        summary='Short-lived individually owned Kubernetes kubeconfig material was generated.',
        outcome='success',
        extra={'namespace': namespace.namespace, 'expires_at': expires_at.isoformat()},
    )
    db.session.commit()
    return GeneratedKubeconfigMaterial(
        credential_public_id=credential.public_id,
        namespace=namespace.namespace,
        expires_at=expires_at,
        access_package=package,
        kubeconfig=rendered,
    )
