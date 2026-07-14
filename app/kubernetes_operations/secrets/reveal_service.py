from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import current_app
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException
from urllib3.exceptions import HTTPError as Urllib3HTTPError

from app.extensions import db
from app.kubernetes.client import KubernetesClient
from app.kubernetes.tls import legacy_tls_context
from app.models import Cluster, ConfigurationInventory, NamespaceInventory, SecretRevealRequest

REVEAL_POLICIES = {
    'disabled': 'Disabled',
    'step_up': 'Step-up authentication',
    'approval_required': 'Approval required',
}

SUPPORTED_REVEAL_TYPES = {
    'Opaque': {
        'label': 'Generic / Opaque',
        'tone': 'blue',
        'icon': 'braces',
    },
    'kubernetes.io/basic-auth': {
        'label': 'Basic Authentication',
        'tone': 'violet',
        'icon': 'badge-user',
    },
    'kubernetes.io/dockerconfigjson': {
        'label': 'Container Registry',
        'tone': 'cyan',
        'icon': 'container',
    },
}

BLOCKED_SECRET_TYPES = {
    'kubernetes.io/service-account-token',
    'kubernetes.io/tls',
    'kubernetes.io/ssh-auth',
}
BLOCKED_KEY_NAMES = {'tls.key', 'ssh-privatekey'}
REQUEST_STATUSES = {'pending', 'approved', 'denied', 'revealed', 'expired'}


@dataclass(frozen=True)
class RevealRequestResult:
    request_record: SecretRevealRequest
    status: str
    title: str
    message: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RevealedSecretValue:
    request_id: str
    key_name: str
    display_value: str
    encoding: str
    revealed_at: datetime
    expires_in_seconds: int
    metadata: dict[str, Any]


def _now() -> datetime:
    return datetime.now(UTC)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _required(value: str | None, label: str, *, max_length: int | None = None) -> str:
    normalized = (value or '').strip()
    if not normalized:
        raise ValueError(f'{label} is required.')
    if max_length is not None and len(normalized) > max_length:
        raise ValueError(f'{label} must be {max_length} characters or fewer.')
    return normalized


def _global_enabled() -> bool:
    return bool(current_app.config.get('KUBERNETES_SECRET_REVEAL_ENABLED', False))


def _cluster_ready(cluster: Cluster) -> bool:
    return bool(
        cluster.secret_reveal_policy in {'step_up', 'approval_required'}
        and cluster.secret_reveal_kubeconfig
        and cluster.secret_reveal_encryption_verified
        and cluster.secret_reveal_audit_verified
    )


def _expire_stale_requests() -> None:
    now = _now()
    candidates = SecretRevealRequest.query.filter(
        SecretRevealRequest.status.in_(('pending', 'approved')),
        SecretRevealRequest.expires_at <= now,
    ).all()
    if not candidates:
        return
    for item in candidates:
        item.status = 'expired'
    db.session.commit()


def get_reveal_clusters() -> list[Cluster]:
    if not _global_enabled():
        return []
    clusters = Cluster.query.order_by(Cluster.name.asc()).all()
    return [cluster for cluster in clusters if _cluster_ready(cluster)]


def get_reveal_workspace(
    cluster_id: str | None,
    namespace: str | None = None,
    inventory_id: str | int | None = None,
) -> dict[str, Any]:
    normalized_cluster_id = (cluster_id or '').strip()
    normalized_namespace = (namespace or '').strip()
    selected_target_id = str(inventory_id or '').strip()
    namespaces: list[str] = []
    targets: list[ConfigurationInventory] = []
    cluster = Cluster.query.filter_by(id=normalized_cluster_id).first() if normalized_cluster_id else None

    cluster_available = bool(_global_enabled() and cluster is not None and _cluster_ready(cluster))
    if cluster_available:
        namespaces = [
            value
            for (value,) in (
                NamespaceInventory.query.with_entities(NamespaceInventory.namespace)
                .filter(NamespaceInventory.cluster_id == normalized_cluster_id)
                .order_by(NamespaceInventory.namespace.asc())
                .all()
            )
        ]

    if cluster_available and normalized_namespace in namespaces:
        targets = (
            ConfigurationInventory.query.filter(
                ConfigurationInventory.cluster_id == normalized_cluster_id,
                ConfigurationInventory.namespace == normalized_namespace,
                ConfigurationInventory.object_type == 'Secret',
                ConfigurationInventory.secret_type.in_(tuple(SUPPORTED_REVEAL_TYPES)),
            )
            .order_by(ConfigurationInventory.name.asc())
            .all()
        )

    return {
        'cluster_id': normalized_cluster_id if cluster_available else '',
        'namespace': normalized_namespace if normalized_namespace in namespaces else '',
        'namespaces': namespaces,
        'targets': targets,
        'selected_target_id': selected_target_id,
        'selected_cluster': cluster if cluster_available else None,
    }


def get_reveal_target(inventory_id: str | int | None) -> ConfigurationInventory | None:
    normalized_id = str(inventory_id or '').strip()
    if not normalized_id.isdigit():
        return None
    target = ConfigurationInventory.query.filter_by(
        id=int(normalized_id),
        object_type='Secret',
    ).first()
    if target is None or target.secret_type not in SUPPORTED_REVEAL_TYPES:
        return None
    return target


def _allowed_keys(target: ConfigurationInventory) -> list[str]:
    return sorted(
        {
            str(key).strip()
            for key in (target.key_names or [])
            if str(key).strip() and str(key).strip() not in BLOCKED_KEY_NAMES
        }
    )


def get_reveal_target_context(inventory_id: str | int | None) -> dict[str, Any]:
    target = get_reveal_target(inventory_id)
    if target is None:
        return {'target': None, 'type_config': None, 'key_names': [], 'selected_cluster': None}
    cluster = Cluster.query.filter_by(id=target.cluster_id).first()
    if cluster is None or not _global_enabled() or not _cluster_ready(cluster):
        return {'target': None, 'type_config': None, 'key_names': [], 'selected_cluster': None}
    return {
        'target': target,
        'type_config': SUPPORTED_REVEAL_TYPES[target.secret_type],
        'key_names': _allowed_keys(target),
        'selected_cluster': cluster,
    }


def get_reveal_page_context(*, user_id: int, can_approve: bool) -> dict[str, Any]:
    _expire_stale_requests()
    my_requests = (
        SecretRevealRequest.query.filter_by(requester_user_id=user_id)
        .order_by(SecretRevealRequest.requested_at.desc())
        .limit(20)
        .all()
    )
    pending_requests: list[SecretRevealRequest] = []
    if can_approve:
        pending_requests = (
            SecretRevealRequest.query.filter_by(status='pending')
            .order_by(SecretRevealRequest.requested_at.asc())
            .limit(50)
            .all()
        )
    return {
        'global_reveal_enabled': _global_enabled(),
        'clusters': get_reveal_clusters(),
        'my_reveal_requests': my_requests,
        'pending_reveal_requests': pending_requests,
        'reveal_policies': REVEAL_POLICIES,
        'reveal_window_seconds': int(
            current_app.config.get('KUBERNETES_SECRET_REVEAL_WINDOW_SECONDS', 15)
        ),
    }


def create_reveal_request(
    form: Any,
    *,
    requester_user_id: int,
    requester_ip: str | None,
) -> RevealRequestResult:
    if not _global_enabled():
        raise ValueError('Protected Secret Reveal is disabled globally.')

    inventory_id = _required(form.get('inventory_id'), 'Secret target')
    target = get_reveal_target(inventory_id)
    if target is None:
        raise ValueError('Selected Secret inventory record was not found or is not revealable.')
    if target.secret_type in BLOCKED_SECRET_TYPES:
        raise ValueError('This Secret type cannot be revealed. Use the dedicated rotation workflow.')

    cluster = Cluster.query.filter_by(id=target.cluster_id).first()
    if cluster is None or not _cluster_ready(cluster):
        raise ValueError('Protected Secret Reveal is not enabled and verified for this cluster.')

    submitted_cluster_id = _required(form.get('cluster_id'), 'Cluster')
    submitted_namespace = _required(form.get('namespace'), 'Namespace')
    if submitted_cluster_id != str(target.cluster_id) or submitted_namespace != target.namespace:
        raise ValueError('The submitted cluster or namespace does not match the selected Secret snapshot.')

    key_name = _required(form.get('key_name'), 'Secret key', max_length=255)
    if key_name not in _allowed_keys(target):
        raise ValueError('The selected key is unavailable or protected from plaintext reveal.')

    reason = _required(form.get('reason'), 'Reason', max_length=1000)
    if len(reason) < 10:
        raise ValueError('Reason must contain at least 10 characters.')
    ticket_reference = _required(form.get('ticket_reference'), 'Ticket or reference', max_length=120)

    now = _now()
    existing_request = SecretRevealRequest.query.filter(
        SecretRevealRequest.requester_user_id == requester_user_id,
        SecretRevealRequest.cluster_id == cluster.id,
        SecretRevealRequest.namespace == target.namespace,
        SecretRevealRequest.secret_name == target.name,
        SecretRevealRequest.key_name == key_name,
        SecretRevealRequest.status.in_(('pending', 'approved')),
        SecretRevealRequest.expires_at > now,
    ).first()
    if existing_request is not None:
        raise ValueError('An active reveal request already exists for this Secret key.')

    if cluster.secret_reveal_policy == 'approval_required':
        status = 'pending'
        expires_at = now + timedelta(
            hours=int(current_app.config.get('KUBERNETES_SECRET_REVEAL_PENDING_TTL_HOURS', 24))
        )
        title = 'Secret reveal request submitted'
        message = 'An authorized approver must approve this request before the value can be revealed.'
    elif cluster.secret_reveal_policy == 'step_up':
        status = 'approved'
        expires_at = now + timedelta(
            minutes=int(current_app.config.get('KUBERNETES_SECRET_REVEAL_APPROVAL_TTL_MINUTES', 10))
        )
        title = 'Secret reveal request ready'
        message = 'Reauthenticate and use the one-time reveal action before the request expires.'
    else:
        raise ValueError('Protected Secret Reveal is disabled for this cluster.')

    record = SecretRevealRequest(
        configuration_inventory_id=target.id,
        cluster_id=cluster.id,
        namespace=target.namespace,
        secret_name=target.name,
        secret_type=target.secret_type or 'Opaque',
        key_name=key_name,
        policy=cluster.secret_reveal_policy,
        reason=reason,
        ticket_reference=ticket_reference,
        status=status,
        requester_user_id=requester_user_id,
        requester_ip=requester_ip,
        requested_at=now,
        expires_at=expires_at,
    )
    db.session.add(record)
    db.session.commit()

    return RevealRequestResult(
        request_record=record,
        status='success',
        title=title,
        message=message,
        metadata={
            'reveal_request_id': record.id,
            'configuration_inventory_id': target.id,
            'cluster_id': cluster.id,
            'cluster_name': cluster.name,
            'namespace': target.namespace,
            'secret_name': target.name,
            'secret_type': target.secret_type,
            'key_name': key_name,
            'policy': cluster.secret_reveal_policy,
            'ticket_reference': ticket_reference,
            'reason': reason,
            'request_status': status,
            'secret_value_recorded': False,
        },
    )


def decide_reveal_request(
    request_id: str,
    *,
    approver_user_id: int,
    approve: bool,
    decision_note: str | None,
) -> SecretRevealRequest:
    _expire_stale_requests()
    record = SecretRevealRequest.query.filter_by(id=request_id).first()
    if record is None:
        raise ValueError('Secret reveal request was not found.')
    if record.status != 'pending':
        raise ValueError('Only pending reveal requests can be approved or denied.')
    if record.requester_user_id == approver_user_id:
        raise ValueError('Requestors cannot approve or deny their own Secret reveal requests.')

    now = _now()
    record.approver_user_id = approver_user_id
    record.decided_at = now
    record.decision_note = (decision_note or '').strip()[:500] or None
    if approve:
        record.status = 'approved'
        record.expires_at = now + timedelta(
            minutes=int(current_app.config.get('KUBERNETES_SECRET_REVEAL_APPROVAL_TTL_MINUTES', 10))
        )
    else:
        record.status = 'denied'
        record.expires_at = now
    db.session.commit()
    return record


def get_reveal_request_for_user(
    request_id: str,
    *,
    user_id: int,
    lock_for_update: bool = False,
) -> SecretRevealRequest:
    _expire_stale_requests()
    query = SecretRevealRequest.query.filter_by(id=request_id)
    if lock_for_update:
        # Serialize one-time consumption in PostgreSQL. The row lock is held until
        # the successful reveal marks the request as revealed and commits.
        query = query.with_for_update()
    record = query.first()
    if record is None:
        raise ValueError('Secret reveal request was not found.')
    if record.requester_user_id != user_id:
        raise ValueError('This reveal request belongs to another user.')
    if record.status != 'approved':
        if record.status == 'revealed':
            raise ValueError('This one-time reveal request has already been used.')
        if record.status == 'expired':
            raise ValueError('This Secret reveal request has expired.')
        raise ValueError('This Secret reveal request is not approved.')
    expires_at = _as_aware(record.expires_at)
    if expires_at is None or expires_at <= _now():
        record.status = 'expired'
        db.session.commit()
        raise ValueError('This Secret reveal request has expired.')
    return record


def _api_error_message(exc: ApiException) -> str:
    status = getattr(exc, 'status', None)
    if status == 404:
        return 'The selected Secret no longer exists in Kubernetes. Refresh inventory before retrying.'
    if status == 403:
        return 'The dedicated Kubernetes credential is not authorized to get this Secret.'
    if status == 401:
        return 'Kubernetes authentication failed for the dedicated reveal credential.'
    if status == 429:
        return 'Kubernetes temporarily rate-limited the reveal request. Retry later.'
    return 'Kubernetes API rejected the protected Secret read operation.'


def _decode_secret_value(encoded_value: str) -> tuple[str, str]:
    try:
        raw = base64.b64decode(encoded_value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError('Kubernetes returned an invalid encoded Secret value.') from exc

    max_bytes = int(current_app.config.get('KUBERNETES_SECRET_REVEAL_MAX_BYTES', 65536))
    if len(raw) > max_bytes:
        raise ValueError(
            f'The selected Secret value exceeds the protected reveal limit of {max_bytes} bytes.'
        )

    try:
        decoded = raw.decode('utf-8')
    except UnicodeDecodeError:
        return base64.b64encode(raw).decode('ascii'), 'base64'

    if any(ord(character) < 9 or 13 < ord(character) < 32 for character in decoded):
        return base64.b64encode(raw).decode('ascii'), 'base64'
    return decoded, 'utf-8'


def reveal_secret_value(request_id: str, *, user_id: int) -> RevealedSecretValue:
    record = get_reveal_request_for_user(
        request_id,
        user_id=user_id,
        lock_for_update=True,
    )
    cluster = Cluster.query.filter_by(id=record.cluster_id).first()
    if cluster is None or not _global_enabled() or not _cluster_ready(cluster):
        raise ValueError('Protected Secret Reveal is no longer enabled for this cluster.')

    target = ConfigurationInventory.query.filter_by(
        id=record.configuration_inventory_id,
        cluster_id=record.cluster_id,
        namespace=record.namespace,
        name=record.secret_name,
        object_type='Secret',
    ).first()
    if target is None or record.key_name not in _allowed_keys(target):
        raise ValueError('The Secret snapshot or selected key changed. Submit a new reveal request.')

    secret_object = None
    secret_data: dict[str, str] = {}
    try:
        with legacy_tls_context(enabled=bool(cluster.kube_allow_weak_tls)):
            api = KubernetesClient(
                cluster.secret_reveal_kubeconfig or '',
                verify_ssl=bool(cluster.kube_verify_ssl),
            ).core_api()
            secret_object = api.read_namespaced_secret(
                name=record.secret_name,
                namespace=record.namespace,
                _request_timeout=10,
            )
        secret_data = dict(getattr(secret_object, 'data', None) or {})
        encoded_value = secret_data.get(record.key_name)
        if encoded_value is None:
            raise ValueError('The selected key no longer exists in the Kubernetes Secret.')
        display_value, encoding = _decode_secret_value(encoded_value)
    except ApiException as exc:
        raise ValueError(_api_error_message(exc)) from exc
    except ConfigException as exc:
        raise ValueError('The dedicated Secret Reveal kubeconfig is invalid or incomplete.') from exc
    except (OSError, Urllib3HTTPError) as exc:
        raise ValueError(
            'KAORI could not reach the Kubernetes API using the dedicated reveal credential.'
        ) from exc
    finally:
        for key in list(secret_data):
            secret_data[key] = ''
        secret_data.clear()
        object_data = getattr(secret_object, 'data', None)
        if isinstance(object_data, dict):
            for key in list(object_data):
                object_data[key] = ''
            object_data.clear()

    revealed_at = _now()
    record.status = 'revealed'
    record.revealed_at = revealed_at
    db.session.commit()

    window_seconds = int(current_app.config.get('KUBERNETES_SECRET_REVEAL_WINDOW_SECONDS', 15))
    return RevealedSecretValue(
        request_id=record.id,
        key_name=record.key_name,
        display_value=display_value,
        encoding=encoding,
        revealed_at=revealed_at,
        expires_in_seconds=window_seconds,
        metadata={
            'reveal_request_id': record.id,
            'configuration_inventory_id': record.configuration_inventory_id,
            'cluster_id': cluster.id,
            'cluster_name': cluster.name,
            'namespace': record.namespace,
            'secret_name': record.secret_name,
            'secret_type': record.secret_type,
            'key_name': record.key_name,
            'policy': record.policy,
            'ticket_reference': record.ticket_reference,
            'reason': record.reason,
            'requester_user_id': record.requester_user_id,
            'approver_user_id': record.approver_user_id,
            'secret_value_recorded': False,
            'secret_value_hash_recorded': False,
        },
    )
