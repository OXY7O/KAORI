from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from flask import current_app
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException
from sqlalchemy import and_, case, func, or_
from urllib3.exceptions import HTTPError as Urllib3HTTPError

from app.common.kubernetes_secrets import scrub_mapping_values, scrub_secret_payload
from app.common.pagination import PER_PAGE_OPTIONS, build_pagination_window, paginate_query, pagination_payload
from app.extensions.db import db
from app.kubernetes.operations.secrets.live_service import (
    LiveSecretSnapshot,
    best_effort_inventory_id,
    core_api,
    list_live_secrets,
    read_live_secret,
)
from app.kubernetes.operations.secrets.reveal_policy import (
    REVEAL_NAMESPACE_POLICIES,
    cluster_reveal_readiness,
    get_configured_enabled_namespace_names,
    get_enabled_namespace_names,
    get_namespace_policy,
)
from app.kubernetes.operations.secrets.reveal_policy import (
    _as_aware as _as_aware,
)
from app.kubernetes.operations.secrets.reveal_policy import (
    _lock_active_request_scope as _lock_active_request_scope,
)
from app.kubernetes.operations.secrets.reveal_policy import (
    get_secret_reveal_approvers as get_secret_reveal_approvers,
)
from app.models import Cluster, SecretRevealNamespacePolicy, SecretRevealRequest
from app.platform_operations.notifications.feedback import OperationalActionPresentation, OperationalDeliveryPolicy
from app.platform_operations.notifications.service import stage_operational_activity

SUPPORTED_REVEAL_TYPES = {
    'Opaque': {
        'label': 'Generic / Opaque',
        'tone': 'blue',
        'icon': 'code',
    },
    'kubernetes.io/basic-auth': {
        'label': 'Basic Authentication',
        'tone': 'violet',
        'icon': 'user',
    },
    'kubernetes.io/dockerconfigjson': {
        'label': 'Container Registry',
        'tone': 'cyan',
        'icon': 'boxes',
    },
}

BLOCKED_SECRET_TYPES = {
    'kubernetes.io/service-account-token',
    'kubernetes.io/tls',
    'kubernetes.io/ssh-auth',
}
BLOCKED_KEY_NAMES = {'tls.key', 'ssh-privatekey'}
REQUEST_STATUSES = {'pending', 'approved', 'denied', 'revealed', 'expired'}


class ActiveRevealRequestExists(ValueError):
    """Raised when the requester already has a pending or approved request."""

    def __init__(self, request_record: SecretRevealRequest) -> None:
        self.request_record = request_record
        super().__init__(
            'You already have an active reveal request for this Secret key. '
            'Continue the existing request or wait until it expires.'
        )


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
    audit_feedback: dict[str, Any] | None = None


def _now() -> datetime:
    return datetime.now(UTC)


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
    return cluster_reveal_readiness(cluster)


def rollback_secret_reveal_transaction() -> None:
    """Reset a failed protected-secret transaction before reading or recording follow-up evidence."""
    db.session.rollback()


def get_reveal_clusters() -> list[Cluster]:
    if not _global_enabled():
        return []
    clusters = Cluster.query.order_by(Cluster.name.asc()).all()
    return [
        cluster
        for cluster in clusters
        if _cluster_ready(cluster) and get_configured_enabled_namespace_names(cluster.id)
    ]


def get_reveal_workspace(
    cluster_id: str | None,
    namespace: str | None = None,
    secret_name: str | None = None,
) -> dict[str, Any]:
    normalized_cluster_id = (cluster_id or '').strip()
    normalized_namespace = (namespace or '').strip()
    selected_secret_name = (secret_name or '').strip()
    namespaces: list[str] = []
    targets = []
    selection_error = None
    selection_error_title = None
    cluster = Cluster.query.filter_by(id=normalized_cluster_id).first() if normalized_cluster_id else None

    cluster_available = bool(_global_enabled() and cluster is not None and _cluster_ready(cluster))
    configured_names: list[str] = []
    if cluster_available:
        configured_names = get_configured_enabled_namespace_names(normalized_cluster_id)
        try:
            namespaces = get_enabled_namespace_names(normalized_cluster_id)
        except ValueError as exc:
            selection_error = str(exc)
            selection_error_title = 'Enabled namespace verification failed'
            normalized_namespace = ''
            selected_secret_name = ''
        else:
            if normalized_namespace not in namespaces:
                normalized_namespace = ''
                selected_secret_name = ''
            if normalized_namespace:
                try:
                    targets = list_live_secrets(
                        normalized_cluster_id,
                        normalized_namespace,
                        supported_types=set(SUPPORTED_REVEAL_TYPES),
                        blocked_types=BLOCKED_SECRET_TYPES,
                    )
                except ValueError as exc:
                    selection_error = str(exc)
                    selection_error_title = 'Live Secret lookup failed'
                    selected_secret_name = ''
                else:
                    live_names = {item.name for item in targets}
                    if selected_secret_name not in live_names:
                        selected_secret_name = ''

    return {
        'cluster_id': normalized_cluster_id if cluster_available else '',
        'namespace': normalized_namespace,
        'namespaces': namespaces,
        'configured_namespace_count': len(configured_names),
        'targets': targets,
        'selected_secret_name': selected_secret_name,
        'selected_cluster': cluster if cluster_available else None,
        'selected_namespace_policy': (
            get_namespace_policy(normalized_cluster_id, normalized_namespace)
            if cluster_available and normalized_namespace in namespaces
            else 'disabled'
        ),
        'selection_error': selection_error,
        'selection_error_title': selection_error_title,
    }


def _allowed_keys(target: LiveSecretSnapshot) -> list[str]:
    return sorted(
        {str(key).strip() for key in target.key_names if str(key).strip() and str(key).strip() not in BLOCKED_KEY_NAMES}
    )


def get_reveal_target_context(
    cluster_id: str | None,
    namespace: str | None,
    secret_name: str | None,
) -> dict[str, Any]:
    if not all(((cluster_id or '').strip(), (namespace or '').strip(), (secret_name or '').strip())):
        return {
            'target': None,
            'type_config': None,
            'key_names': [],
            'selected_cluster': None,
            'selected_namespace_policy': 'disabled',
            'target_error': None,
        }
    try:
        target = read_live_secret(
            cluster_id,
            namespace,
            secret_name,
            supported_types=set(SUPPORTED_REVEAL_TYPES),
            blocked_types=BLOCKED_SECRET_TYPES,
        )
    except ValueError as exc:
        return {
            'target': None,
            'type_config': None,
            'key_names': [],
            'selected_cluster': None,
            'selected_namespace_policy': 'disabled',
            'target_error': str(exc),
        }

    namespace_policy = get_namespace_policy(target.cluster_id, target.namespace)
    if (
        not _global_enabled()
        or not _cluster_ready(target.cluster)
        or namespace_policy not in {'step_up', 'approval_required'}
    ):
        return {
            'target': None,
            'type_config': None,
            'key_names': [],
            'selected_cluster': None,
            'selected_namespace_policy': 'disabled',
            'target_error': 'Protected Secret Reveal is disabled for the selected live target.',
        }
    return {
        'target': target,
        'type_config': SUPPORTED_REVEAL_TYPES.get(target.secret_type),
        'key_names': _allowed_keys(target),
        'selected_cluster': target.cluster,
        'selected_namespace_policy': namespace_policy,
        'target_error': None,
    }


@dataclass(frozen=True, slots=True)
class PendingRevealPagination:
    page: int = 1
    per_page: int = 5


@dataclass(frozen=True, slots=True)
class MyRevealFilters:
    page: int = 1
    per_page: int = 5
    search: str = ''
    status: str = ''
    sort: str = 'newest'
    request_id: str = ''


@dataclass(frozen=True, slots=True)
class PendingRevealFilters:
    pagination: PendingRevealPagination = PendingRevealPagination()
    search: str = ''
    sort: str = 'oldest'


def get_reveal_page_context(
    *,
    user_id: int,
    can_approve: bool,
    my_filters: MyRevealFilters = MyRevealFilters(),
    pending_filters: PendingRevealFilters = PendingRevealFilters(),
) -> dict[str, Any]:

    now = _now()
    effective_status = case(
        (
            and_(
                SecretRevealRequest.status.in_(('pending', 'approved')),
                SecretRevealRequest.expires_at <= now,
            ),
            'expired',
        ),
        else_=SecretRevealRequest.status,
    )
    # Restrict to the requester first; filtering is SQL-backed and never reads Secret values.
    search = str(my_filters.search or '').strip()[:120]
    allowed_statuses = {'pending', 'approved', 'revealed', 'denied', 'expired'}
    state_filter = str(my_filters.status or '').strip().lower()
    if state_filter not in allowed_statuses:
        state_filter = ''
    ordering = 'oldest' if my_filters.sort == 'oldest' else 'newest'

    # Exact linked-request selection is strictly scoped to the current requester.
    # Notification IDs never convey authority or permit another user's request reads.
    focus_id = str(my_filters.request_id or '').strip()[:80]
    my_query = SecretRevealRequest.query.filter_by(requester_user_id=user_id)
    if focus_id:
        my_query = my_query.filter(SecretRevealRequest.id == focus_id)
    if search:
        search_term = search.lower()
        my_query = my_query.filter(
            or_(
                func.lower(SecretRevealRequest.secret_name).contains(search_term, autoescape=True),
                func.lower(SecretRevealRequest.key_name).contains(search_term, autoescape=True),
                func.lower(SecretRevealRequest.namespace).contains(search_term, autoescape=True),
                func.lower(SecretRevealRequest.ticket_reference).contains(search_term, autoescape=True),
            )
        )
    if state_filter:
        my_query = my_query.filter(effective_status == state_filter)
    if ordering == 'oldest':
        my_query = my_query.order_by(SecretRevealRequest.requested_at.asc(), SecretRevealRequest.id.asc())
    else:
        my_query = my_query.order_by(SecretRevealRequest.requested_at.desc(), SecretRevealRequest.id.desc())
    my_requests, my_window = paginate_query(my_query, page=my_filters.page, per_page=my_filters.per_page)
    # Preserve the existing Reveal template keys without keeping a separate
    # page-size policy or a second hand-written pagination algorithm.
    my_pagination = {
        **my_window,
        'total': my_window['total_items'],
        'pages': my_window['total_pages'],
        'start': my_window['start_item'],
        'end': my_window['end_item'],
        'page_sizes': PER_PAGE_OPTIONS,
    }

    # The approval permission boundary precedes all searches/pagination.
    # Only request metadata is queried; never Secret payloads.
    pending_search_value = str(pending_filters.search or '').strip()[:120]
    pending_ordering = 'newest' if pending_filters.sort == 'newest' else 'oldest'
    pending_requests: list[SecretRevealRequest] = []
    if can_approve:
        pending_query = SecretRevealRequest.query.filter(
            SecretRevealRequest.status == 'pending',
            SecretRevealRequest.expires_at > now,
        )
        if pending_search_value:
            pending_term = pending_search_value.lower()
            pending_query = pending_query.filter(
                or_(
                    func.lower(SecretRevealRequest.secret_name).contains(pending_term, autoescape=True),
                    func.lower(SecretRevealRequest.namespace).contains(pending_term, autoescape=True),
                    func.lower(SecretRevealRequest.key_name).contains(pending_term, autoescape=True),
                    func.lower(SecretRevealRequest.ticket_reference).contains(pending_term, autoescape=True),
                )
            )
        if pending_ordering == 'newest':
            pending_query = pending_query.order_by(
                SecretRevealRequest.requested_at.desc(), SecretRevealRequest.id.desc()
            )
        else:
            pending_query = pending_query.order_by(SecretRevealRequest.requested_at.asc(), SecretRevealRequest.id.asc())
        pending_requests, pending_window = paginate_query(
            pending_query,
            page=pending_filters.pagination.page,
            per_page=pending_filters.pagination.per_page,
        )
    else:
        pending_window = pagination_payload(
            build_pagination_window(
                total_items=0,
                page=pending_filters.pagination.page,
                per_page=pending_filters.pagination.per_page,
            )
        )
    pending_pagination_payload = {
        **pending_window,
        'total': pending_window['total_items'],
        'pages': pending_window['total_pages'],
        'start': pending_window['start_item'],
        'end': pending_window['end_item'],
        'page_sizes': PER_PAGE_OPTIONS,
    }
    configured_reveal_namespace_count = SecretRevealNamespacePolicy.query.filter(
        SecretRevealNamespacePolicy.policy.in_(('step_up', 'approval_required'))
    ).count()

    return {
        'global_reveal_enabled': _global_enabled(),
        'configured_reveal_namespace_count': configured_reveal_namespace_count,
        'clusters': get_reveal_clusters(),
        'my_reveal_requests': my_requests,
        'my_reveal_pagination': my_pagination,
        'my_reveal_filters': {'search': search, 'status': state_filter, 'sort': ordering},
        'my_reveal_focus_id': focus_id,
        'pending_reveal_requests': pending_requests,
        'pending_reveal_pagination': pending_pagination_payload,
        'pending_reveal_filters': {'search': pending_search_value, 'sort': pending_ordering},
        'reveal_policies': REVEAL_NAMESPACE_POLICIES,
        'reveal_window_seconds': int(current_app.config.get('KUBERNETES_SECRET_REVEAL_WINDOW_SECONDS', 15)),
    }


def create_reveal_request(
    form: Any,
    *,
    requester_user_id: int,
    requester_ip: str | None,
) -> RevealRequestResult:
    if not _global_enabled():
        raise ValueError('Protected Secret Reveal is disabled globally.')

    cluster_id = _required(form.get('cluster_id'), 'Cluster')
    namespace = _required(form.get('namespace'), 'Namespace')
    secret_name = _required(form.get('secret_name'), 'Secret target')
    target = read_live_secret(
        cluster_id,
        namespace,
        secret_name,
        supported_types=set(SUPPORTED_REVEAL_TYPES),
        blocked_types=BLOCKED_SECRET_TYPES,
    )
    cluster = target.cluster
    if not _cluster_ready(cluster):
        raise ValueError('Protected Secret Reveal security readiness is not verified for this cluster.')

    namespace_policy = get_namespace_policy(cluster.id, target.namespace)
    if namespace_policy not in {'step_up', 'approval_required'}:
        raise ValueError('Protected Secret Reveal is disabled for the selected namespace.')

    secret_uid = str(target.uid or '').strip()
    if not secret_uid:
        raise ValueError('Kubernetes did not return a Secret UID. Reload the live target before requesting access.')

    key_name = _required(form.get('key_name'), 'Secret key', max_length=255)
    if key_name not in _allowed_keys(target):
        raise ValueError('The selected key is unavailable or protected from plaintext reveal.')

    reason = _required(form.get('reason'), 'Reason', max_length=1000)
    if len(reason) < 10:
        raise ValueError('Reason must contain at least 10 characters.')
    ticket_reference = _required(form.get('ticket_reference'), 'Ticket or reference', max_length=120)

    now = _now()
    _lock_active_request_scope(
        requester_user_id=requester_user_id,
        cluster_id=str(cluster.id),
        namespace=target.namespace,
        secret_name=target.name,
        key_name=key_name,
    )
    existing_request = (
        SecretRevealRequest.query.filter(
            SecretRevealRequest.requester_user_id == requester_user_id,
            SecretRevealRequest.cluster_id == cluster.id,
            SecretRevealRequest.namespace == target.namespace,
            SecretRevealRequest.secret_name == target.name,
            SecretRevealRequest.key_name == key_name,
            SecretRevealRequest.status.in_(('pending', 'approved')),
            or_(
                SecretRevealRequest.expires_at.is_(None),
                SecretRevealRequest.expires_at > now,
            ),
        )
        .order_by(SecretRevealRequest.requested_at.desc())
        .first()
    )
    if existing_request is not None:
        raise ActiveRevealRequestExists(existing_request)

    if namespace_policy == 'approval_required':
        status = 'pending'
        expires_at = now + timedelta(
            hours=int(current_app.config.get('KUBERNETES_SECRET_REVEAL_PENDING_TTL_HOURS', 24))
        )
        title = 'Secret reveal request submitted'
        message = 'An authorized approver must approve this request before the value can be revealed.'
    elif namespace_policy == 'step_up':
        status = 'approved'
        expires_at = now + timedelta(
            minutes=int(current_app.config.get('KUBERNETES_SECRET_REVEAL_APPROVAL_TTL_MINUTES', 10))
        )
        title = 'Secret reveal request ready'
        message = 'Reauthenticate and use the one-time reveal action before the request expires.'
    else:
        raise ValueError('Protected Secret Reveal is disabled for the selected namespace.')

    inventory_id = best_effort_inventory_id(target)
    record = SecretRevealRequest()
    record.configuration_inventory_id = inventory_id
    record.cluster_id = cluster.id
    record.namespace = target.namespace
    record.secret_name = target.name
    record.secret_type = target.secret_type or 'Opaque'
    record.secret_uid = secret_uid
    record.key_name = key_name
    record.policy = namespace_policy
    record.reason = reason
    record.ticket_reference = ticket_reference
    record.status = status
    record.requester_user_id = requester_user_id
    record.requester_ip = requester_ip
    record.requested_at = now
    record.expires_at = expires_at
    db.session.add(record)
    db.session.commit()

    return RevealRequestResult(
        request_record=record,
        status='success',
        title=title,
        message=message,
        metadata={
            'reveal_request_id': record.id,
            'configuration_inventory_id': inventory_id,
            'cluster_id': cluster.id,
            'cluster_name': cluster.name,
            'namespace': target.namespace,
            'secret_name': target.name,
            'secret_type': target.secret_type,
            'key_name': key_name,
            'policy': namespace_policy,
            'ticket_reference': ticket_reference,
            'reason': reason,
            'request_status': status,
            'live_target_source': True,
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
    # Lock only the request table; joined eager relations can trigger an
    # invalid FOR UPDATE on nullable outer joins in PostgreSQL.
    record = (
        SecretRevealRequest.query.filter_by(id=request_id)
        .enable_eagerloads(False)
        .with_for_update(of=SecretRevealRequest)
        .first()
    )
    if record is None:
        raise ValueError('Secret reveal request was not found.')
    if record.status != 'pending':
        raise ValueError('Only pending reveal requests can be approved or denied.')
    if record.requester_user_id == approver_user_id:
        raise ValueError('Requestors cannot approve or deny their own Secret reveal requests.')
    if (expires_at := _as_aware(record.expires_at)) is None or expires_at <= _now():
        raise ValueError('This Secret reveal request has expired.')

    if approve:
        # Approval belongs to the exact live Kubernetes object, not merely
        # the namespace/name tuple. Fail closed for pre-migration requests.
        approved_uid = str(record.secret_uid or '').strip()
        if not approved_uid:
            raise ValueError('This request lacks approved Secret identity evidence. Submit a new request.')
        live_target = read_live_secret(
            record.cluster_id,
            record.namespace,
            record.secret_name,
            supported_types=set(SUPPORTED_REVEAL_TYPES),
            blocked_types=BLOCKED_SECRET_TYPES,
        )
        if str(live_target.uid or '').strip() != approved_uid or live_target.secret_type != record.secret_type:
            raise ValueError('The live Secret identity changed. Submit a new reveal request.')
        if record.key_name not in _allowed_keys(live_target):
            raise ValueError('The approved Secret key is no longer available. Submit a new request.')
        cluster = Cluster.query.filter_by(id=record.cluster_id).first()
        current_policy = get_namespace_policy(record.cluster_id, record.namespace)
        if (
            cluster is None
            or not _global_enabled()
            or not _cluster_ready(cluster)
            or current_policy != 'approval_required'
            or record.policy != current_policy
        ):
            raise ValueError(
                'This request can no longer be approved because the cluster readiness or namespace policy changed.'
            )

    now = _now()
    next_expiry = (
        now + timedelta(minutes=int(current_app.config.get('KUBERNETES_SECRET_REVEAL_APPROVAL_TTL_MINUTES', 10)))
        if approve
        else now
    )
    # Compare-and-set additionally protects engines that ignore FOR UPDATE,
    # and makes duplicate POST submissions fail closed rather than notify twice.
    changed = SecretRevealRequest.query.filter(
        SecretRevealRequest.id == record.id,
        SecretRevealRequest.status == 'pending',
        SecretRevealRequest.expires_at > now,
    ).update(
        {
            SecretRevealRequest.status: 'approved' if approve else 'denied',
            SecretRevealRequest.approver_user_id: approver_user_id,
            SecretRevealRequest.decided_at: now,
            SecretRevealRequest.decision_note: (decision_note or '').strip()[:500] or None,
            SecretRevealRequest.expires_at: next_expiry,
        },
        synchronize_session=False,
    )
    if changed != 1:
        db.session.rollback()
        raise ValueError('This reveal request was already decided or expired. Refresh the approval list.')
    db.session.commit()
    db.session.refresh(record)
    return record


def get_reveal_request_for_user(
    request_id: str,
    *,
    user_id: int,
    lock_for_update: bool = False,
) -> SecretRevealRequest:
    query = SecretRevealRequest.query.filter_by(id=request_id)
    if lock_for_update:
        # Serialize one-time consumption on the request row only. SecretRevealRequest
        # owns joined relationships (including nullable approver/inventory joins); a
        # broad FOR UPDATE over those OUTER JOINs is rejected by PostgreSQL. The reveal
        # path only needs scalar request identity before loading its live Cluster
        # explicitly, so suppress eager joins and lock the request table itself.
        query = query.enable_eagerloads(False).with_for_update(of=SecretRevealRequest)
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
        raise ValueError('This Secret reveal request has expired.')
    return record


def _api_error_message(exc: ApiException) -> str:
    status = getattr(exc, 'status', None)
    if status == 404:
        return 'The selected Secret no longer exists in Kubernetes. Reload the live target before retrying.'
    if status == 403:
        return 'The cluster kubeconfig identity is not authorized to get this Secret.'
    if status == 401:
        return 'Kubernetes authentication failed for the cluster kubeconfig identity.'
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
        raise ValueError(f'The selected Secret value exceeds the protected reveal limit of {max_bytes} bytes.')

    try:
        decoded = raw.decode('utf-8')
    except UnicodeDecodeError:
        return base64.b64encode(raw).decode('ascii'), 'base64'

    if any(ord(character) < 9 or 13 < ord(character) < 32 for character in decoded):
        return base64.b64encode(raw).decode('ascii'), 'base64'
    return decoded, 'utf-8'


def reveal_secret_value(request_id: str, *, user_id: int, audit_action_url: str | None = None) -> RevealedSecretValue:
    record = get_reveal_request_for_user(
        request_id,
        user_id=user_id,
        lock_for_update=True,
    )
    cluster = Cluster.query.filter_by(id=record.cluster_id).first()
    if cluster is None or not _global_enabled() or not _cluster_ready(cluster):
        raise ValueError('Protected Secret Reveal is no longer ready for this cluster.')

    current_policy = get_namespace_policy(record.cluster_id, record.namespace)
    if current_policy not in {'step_up', 'approval_required'}:
        raise ValueError('Protected Secret Reveal is no longer enabled for this namespace.')
    if current_policy != record.policy:
        raise ValueError('The namespace Reveal policy changed. Submit a new reveal request.')

    secret_object = None
    secret_data: dict[str, str] = {}
    try:
        secret_object = core_api(cluster).read_namespaced_secret(
            name=record.secret_name,
            namespace=record.namespace,
            _request_timeout=10,
        )
        live_metadata = getattr(secret_object, 'metadata', None)
        live_uid = str(getattr(live_metadata, 'uid', None) or '').strip()
        approved_uid = str(record.secret_uid or '').strip()
        if not approved_uid or live_uid != approved_uid:
            raise ValueError('The approved Secret object was replaced or its identity cannot be verified.')
        live_secret_type = str(getattr(secret_object, 'type', None) or 'Opaque')
        if live_secret_type != record.secret_type:
            raise ValueError('The approved Secret type changed. Submit a new reveal request.')
        if live_secret_type not in SUPPORTED_REVEAL_TYPES or live_secret_type in BLOCKED_SECRET_TYPES:
            raise ValueError('The live Secret type is no longer revealable. Submit a new request after review.')
        if record.key_name in BLOCKED_KEY_NAMES:
            raise ValueError('The selected key is protected from plaintext reveal.')
        secret_data = dict(getattr(secret_object, 'data', None) or {})
        encoded_value = secret_data.get(record.key_name)
        if encoded_value is None:
            raise ValueError('The selected key no longer exists in the Kubernetes Secret.')
        display_value, encoding = _decode_secret_value(encoded_value)
    except ApiException as exc:
        raise ValueError(_api_error_message(exc)) from exc
    except ConfigException as exc:
        raise ValueError('The cluster kubeconfig is invalid or incomplete.') from exc
    except (OSError, Urllib3HTTPError) as exc:
        raise ValueError('KAORI could not reach the Kubernetes API using the cluster kubeconfig.') from exc
    finally:
        scrub_mapping_values(secret_data)
        scrub_secret_payload(secret_object)

    revealed_at = _now()
    record.status = 'revealed'
    record.revealed_at = revealed_at
    window_seconds = int(current_app.config.get('KUBERNETES_SECRET_REVEAL_WINDOW_SECONDS', 15))
    safe_metadata = {
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
        'feedback_delivery': 'toast',
        'operation_domain': 'kubernetes_secrets',
    }
    try:
        # This evidence and the one-time consumption share ONE commit.
        # A failed Activity Audit cannot produce a successful Secret response.
        audit_feedback = stage_operational_activity(
            user_id=user_id,
            event_type='kubernetes_secret_revealed',
            status='success',
            title='Secret value revealed',
            message=(
                f'{record.key_name} was revealed once for {window_seconds} seconds. The value was not stored by KAORI.'
            ),
            action_url=audit_action_url,
            action=OperationalActionPresentation(label='Open Protected Secret Reveal', icon='key'),
            metadata=safe_metadata,
            delivery_policy=OperationalDeliveryPolicy.AUDIT_ONLY,
        )
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        raise ValueError('Mandatory Activity Audit could not be committed. The Secret value was not returned.') from exc

    return RevealedSecretValue(
        request_id=record.id,
        key_name=record.key_name,
        display_value=display_value,
        encoding=encoding,
        revealed_at=revealed_at,
        expires_in_seconds=window_seconds,
        metadata=safe_metadata,
        audit_feedback=audit_feedback,
    )
