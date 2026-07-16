from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any, cast

from kubernetes.client import V1NamespaceList, V1ObjectMeta, V1Secret
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException
from urllib3.exceptions import HTTPError as Urllib3HTTPError

from app.kubernetes.client import KubernetesClient
from app.kubernetes.secrets.tls import validate_certificate_pair
from app.kubernetes.tls import legacy_tls_context
from app.models import Cluster

SECRET_TYPE_LABELS = {
    'opaque': 'Generic / Opaque',
    'basic-auth': 'Basic Authentication',
    'tls': 'TLS Certificate',
    'dockerconfigjson': 'Container Registry',
    'ssh-auth': 'SSH Authentication',
}

SECRET_KUBERNETES_TYPES = {
    'opaque': 'Opaque',
    'basic-auth': 'kubernetes.io/basic-auth',
    'tls': 'kubernetes.io/tls',
    'dockerconfigjson': 'kubernetes.io/dockerconfigjson',
    'ssh-auth': 'kubernetes.io/ssh-auth',
}

_DNS_LABEL_PATTERN = re.compile(r'^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$')
_SECRET_DATA_KEY_PATTERN = re.compile(r'^[-._a-zA-Z0-9]+$')
_EMAIL_PATTERN = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
_MAX_KUBERNETES_SECRET_BYTES = 1024 * 1024
_MAX_UPLOAD_BYTES = 1024 * 1024


@dataclass(frozen=True)
class SecretOperationResult:
    status: str
    title: str
    message: str
    detail: str | None
    metadata: dict[str, Any]


def get_secret_create_context() -> dict[str, Any]:
    """Return stable Create Secret page context.

    Registered clusters come from KAORI's cluster registry. Namespace choices are
    intentionally loaded on demand from the selected cluster's live Kubernetes
    API and are therefore not preloaded from inventory snapshots here.
    """
    return {
        'clusters': Cluster.query.order_by(Cluster.name.asc()).all(),
        'namespace_options': {},
        'secret_types': SECRET_TYPE_LABELS,
    }


def _cluster(cluster_id: str) -> Cluster:
    cluster = Cluster.query.filter_by(id=cluster_id).first()
    if cluster is None:
        raise ValueError('The selected Kubernetes cluster is no longer available.')
    return cluster


def _core_api(cluster: Cluster):
    return KubernetesClient(
        cluster.kubeconfig,
        verify_ssl=bool(cluster.kube_verify_ssl),
    ).core_api()


def get_cluster_namespace_options(cluster_id: str | None) -> list[str]:
    """Return namespaces directly from the selected Kubernetes API server."""
    normalized_cluster_id = (cluster_id or '').strip()
    if not normalized_cluster_id:
        return []

    cluster = _cluster(normalized_cluster_id)
    try:
        with legacy_tls_context(enabled=bool(cluster.kube_allow_weak_tls)):
            response = cast(V1NamespaceList, _core_api(cluster).list_namespace())
    except ApiException as exc:
        if exc.status == 403:
            raise ValueError(
                'Kubernetes denied the live namespace lookup. Verify namespace list RBAC for this cluster.'
            ) from exc
        if exc.status == 401:
            raise ValueError(
                'Kubernetes authentication failed while loading live namespaces.'
            ) from exc
        raise ValueError(
            'KAORI could not load live namespaces from the selected Kubernetes cluster.'
        ) from exc
    except ConfigException as exc:
        raise ValueError('The selected cluster kubeconfig is invalid or incomplete.') from exc
    except (OSError, Urllib3HTTPError) as exc:
        raise ValueError(
            'KAORI could not reach the Kubernetes API while loading live namespaces.'
        ) from exc

    return sorted(
        item.metadata.name
        for item in (response.items or [])
        if getattr(getattr(item, 'metadata', None), 'name', None)
    )


def _required(value: str | None, label: str) -> str:
    normalized = (value or '').strip()
    if not normalized:
        raise ValueError(f'{label} is required.')
    return normalized


def _validate_secret_name(name: str) -> None:
    labels = name.split('.')
    invalid_label = any(
        not label or len(label) > 63 or not _DNS_LABEL_PATTERN.fullmatch(label)
        for label in labels
    )
    if len(name) > 253 or invalid_label:
        raise ValueError(
            'Secret name must be a valid lowercase DNS subdomain using letters, numbers, dots, or hyphens.'
        )


def _validate_namespace_name(namespace: str) -> None:
    if len(namespace) > 63 or not _DNS_LABEL_PATTERN.fullmatch(namespace):
        raise ValueError(
            'Namespace must be a valid lowercase Kubernetes namespace name.'
        )


def _validate_namespace_target(cluster: Cluster, namespace: str) -> None:
    """Verify the submitted namespace against the live Kubernetes API."""
    try:
        with legacy_tls_context(enabled=bool(cluster.kube_allow_weak_tls)):
            _core_api(cluster).read_namespace(name=namespace)
    except ApiException as exc:
        if exc.status == 404:
            raise ValueError(
                'The selected namespace no longer exists in the Kubernetes cluster.'
            ) from exc
        if exc.status == 403:
            raise ValueError(
                'Kubernetes denied namespace verification. Verify namespace read RBAC for this cluster.'
            ) from exc
        if exc.status == 401:
            raise ValueError(
                'Kubernetes authentication failed while verifying the namespace.'
            ) from exc
        raise ValueError(
            'KAORI could not verify the selected namespace against the live Kubernetes cluster.'
        ) from exc
    except ConfigException as exc:
        raise ValueError('The selected cluster kubeconfig is invalid or incomplete.') from exc
    except (OSError, Urllib3HTTPError) as exc:
        raise ValueError(
            'KAORI could not reach the Kubernetes API while verifying the namespace.'
        ) from exc


def _read_upload(upload: Any, label: str) -> bytes:
    if upload is None or not getattr(upload, 'filename', ''):
        raise ValueError(f'{label} is required.')

    payload = upload.read(_MAX_UPLOAD_BYTES + 1)
    if len(payload) > _MAX_UPLOAD_BYTES:
        raise ValueError(f'{label} must be 1 MiB or smaller.')
    if not payload:
        raise ValueError(f'{label} is empty.')
    return payload


def _decode_utf8(payload: bytes, label: str) -> str:
    try:
        return payload.decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError(f'{label} must use UTF-8 text encoding.') from exc


def _validate_secret_size(string_data: dict[str, str]) -> None:
    payload_size = sum(
        len(key.encode('utf-8')) + len(value.encode('utf-8'))
        for key, value in string_data.items()
    )
    if payload_size >= _MAX_KUBERNETES_SECRET_BYTES:
        raise ValueError('Secret content must be smaller than the Kubernetes 1 MiB limit.')


def _validate_ssh_private_key(raw_key: str) -> None:
    try:
        from cryptography.exceptions import UnsupportedAlgorithm
        from cryptography.hazmat.primitives import serialization
    except ModuleNotFoundError as exc:
        raise ValueError('SSH private-key validation is unavailable on this KAORI instance.') from exc

    key_bytes = raw_key.encode('utf-8')
    try:
        try:
            serialization.load_pem_private_key(key_bytes, password=None)
        except ValueError:
            serialization.load_ssh_private_key(key_bytes, password=None)
    except (TypeError, ValueError, UnsupportedAlgorithm) as exc:
        raise ValueError(
            'SSH private key must be a valid, unencrypted PEM or OpenSSH private key.'
        ) from exc


def _build_string_data(form: Any, files: Any, secret_type: str) -> tuple[dict[str, str], dict[str, Any]]:
    metadata: dict[str, Any] = {}
    if secret_type == 'opaque':
        keys = form.getlist('generic_key')
        values = form.getlist('generic_value')
        if len(keys) != len(values):
            raise ValueError('Generic Secret key-value entries are incomplete.')

        string_data: dict[str, str] = {}
        for key, value in zip(keys, values, strict=True):
            normalized_key = key.strip()
            if not normalized_key:
                continue
            if len(normalized_key) > 253 or not _SECRET_DATA_KEY_PATTERN.fullmatch(normalized_key):
                raise ValueError(
                    f'Invalid Secret data key: {normalized_key}. Use letters, numbers, dots, hyphens, or underscores.'
                )
            if normalized_key in string_data:
                raise ValueError(f'Duplicate Secret data key: {normalized_key}.')
            string_data[normalized_key] = value
        if not string_data:
            raise ValueError('Add at least one key-value entry.')
        metadata['key_names'] = sorted(string_data)
        _validate_secret_size(string_data)
        return string_data, metadata

    if secret_type == 'basic-auth':
        username = _required(form.get('username'), 'Username')
        password = _required(form.get('password'), 'Password')
        if password != (form.get('password_confirm') or ''):
            raise ValueError('Password confirmation does not match.')
        string_data = {'username': username, 'password': password}
        metadata['key_names'] = ['username', 'password']
        _validate_secret_size(string_data)
        return string_data, metadata

    if secret_type == 'tls':
        cert_bytes = _read_upload(files.get('tls_crt_file'), 'Certificate file')
        key_bytes = _read_upload(files.get('tls_key_file'), 'Private key file')
        validation = validate_certificate_pair(cert_bytes, key_bytes)
        if not validation.is_valid:
            raise ValueError(' '.join(validation.errors) or 'Certificate and private key do not match.')
        parsed = validation.parsed_certificate
        string_data = {
            'tls.crt': _decode_utf8(cert_bytes, 'Certificate file'),
            'tls.key': _decode_utf8(key_bytes, 'Private key file'),
        }
        metadata.update({
            'key_names': ['tls.crt', 'tls.key'],
            'certificate_common_name': getattr(parsed, 'common_name', None),
            'certificate_expiry': parsed.not_after.isoformat() if parsed else None,
            'certificate_fingerprint_sha256': getattr(parsed, 'fingerprint_sha256', None),
        })
        _validate_secret_size(string_data)
        return string_data, metadata

    if secret_type == 'dockerconfigjson':
        server = _required(form.get('registry_server'), 'Registry server')
        username = _required(form.get('registry_username'), 'Registry username')
        password = _required(form.get('registry_password'), 'Registry password or token')
        email = (form.get('registry_email') or '').strip()
        if any(character.isspace() for character in server):
            raise ValueError('Registry server must not contain spaces.')
        if email and not _EMAIL_PATTERN.fullmatch(email):
            raise ValueError('Registry email address is invalid.')

        auth = base64.b64encode(f'{username}:{password}'.encode()).decode()
        payload = {'auths': {server: {'username': username, 'password': password, 'auth': auth}}}
        if email:
            payload['auths'][server]['email'] = email
        string_data = {'.dockerconfigjson': json.dumps(payload, separators=(',', ':'))}
        metadata['key_names'] = ['.dockerconfigjson']
        metadata['registry_server'] = server
        _validate_secret_size(string_data)
        return string_data, metadata

    if secret_type == 'ssh-auth':
        key_file = files.get('ssh_private_key_file')
        if key_file is not None and getattr(key_file, 'filename', ''):
            raw_key = _decode_utf8(_read_upload(key_file, 'SSH private key file'), 'SSH private key file')
        else:
            raw_key = _required(form.get('ssh_private_key'), 'SSH private key')
        _validate_ssh_private_key(raw_key)
        string_data = {'ssh-privatekey': raw_key}
        metadata['key_names'] = ['ssh-privatekey']
        _validate_secret_size(string_data)
        return string_data, metadata

    raise ValueError('Unsupported Secret type.')


def _kubernetes_api_error_message(exc: ApiException) -> str:
    status = getattr(exc, 'status', None)
    if status == 409:
        return 'A Secret with this name already exists. Existing data was not changed.'
    if status == 404:
        return 'The selected namespace was not found in the cluster. Refresh the live namespace list and verify the target.'
    if status == 403:
        return 'Kubernetes denied this operation. Verify the cluster credential can create Secrets in this namespace.'
    if status == 401:
        return 'Kubernetes authentication failed for the selected cluster.'
    if status == 422:
        return 'Kubernetes rejected the Secret payload because one or more fields are invalid.'
    if status == 400:
        return 'Kubernetes rejected the Secret request. Review the resource name, type, and content.'

    reason = (getattr(exc, 'reason', None) or '').strip()
    return reason or 'Kubernetes API rejected the Secret operation.'


def execute_secret_operation(form: Any, files: Any, *, dry_run: bool) -> SecretOperationResult:
    cluster_id = _required(form.get('cluster_id'), 'Cluster')
    namespace = _required(form.get('namespace'), 'Namespace')
    name = _required(form.get('secret_name'), 'Secret name')
    secret_type = _required(form.get('secret_type'), 'Secret type')
    immutable_value = (form.get('immutable') or 'false').strip().lower()

    if secret_type not in SECRET_KUBERNETES_TYPES:
        raise ValueError('Unsupported Secret type.')
    if immutable_value not in {'true', 'false'}:
        raise ValueError('Mutability selection is invalid.')

    _validate_secret_name(name)
    _validate_namespace_name(namespace)

    cluster = _cluster(cluster_id)
    _validate_namespace_target(cluster, namespace)

    string_data, safe_metadata = _build_string_data(form, files, secret_type)
    body = V1Secret(
        api_version='v1',
        kind='Secret',
        metadata=V1ObjectMeta(name=name, namespace=namespace),
        immutable=immutable_value == 'true',
        string_data=string_data,
        type=SECRET_KUBERNETES_TYPES[secret_type],
    )

    try:
        with legacy_tls_context(enabled=bool(cluster.kube_allow_weak_tls)):
            api = _core_api(cluster)
            created = api.create_namespaced_secret(
                namespace=namespace,
                body=body,
                dry_run='All' if dry_run else None,
            )
    except ApiException as exc:
        raise ValueError(_kubernetes_api_error_message(exc)) from exc
    except ConfigException as exc:
        raise ValueError('The selected cluster kubeconfig is invalid or incomplete.') from exc
    except (OSError, Urllib3HTTPError) as exc:
        raise ValueError(
            'KAORI could not reach the Kubernetes API for the selected cluster. '
            'Check connectivity and cluster configuration.'
        ) from exc

    operation = 'validation' if dry_run else 'creation'
    return SecretOperationResult(
        status='success',
        title=f'Secret {operation} completed',
        message=(
            f'{name} is valid and ready to create in {cluster.name}/{namespace}.'
            if dry_run
            else f'{name} was created in {cluster.name}/{namespace}.'
        ),
        detail=None,
        metadata={
            'cluster_id': cluster.id,
            'cluster_name': cluster.name,
            'namespace': namespace,
            'secret_name': name,
            'secret_type': SECRET_KUBERNETES_TYPES[secret_type],
            'secret_type_label': SECRET_TYPE_LABELS[secret_type],
            'immutable': body.immutable,
            'operation': operation,
            'resource_uid': getattr(getattr(created, 'metadata', None), 'uid', None),
            'resource_version': getattr(getattr(created, 'metadata', None), 'resource_version', None),
            **safe_metadata,
        },
    )
