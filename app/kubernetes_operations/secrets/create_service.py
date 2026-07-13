from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from kubernetes.client import V1ObjectMeta, V1Secret
from kubernetes.client.exceptions import ApiException

from app.kubernetes.client import KubernetesClient
from app.kubernetes.secrets.tls import validate_certificate_pair
from app.kubernetes.tls import legacy_tls_context
from app.models import Cluster, NamespaceInventory

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


@dataclass(frozen=True)
class SecretOperationResult:
    status: str
    title: str
    message: str
    detail: str | None
    metadata: dict[str, Any]


def get_secret_create_context() -> dict[str, Any]:
    clusters = Cluster.query.order_by(Cluster.name.asc()).all()
    namespaces = NamespaceInventory.query.order_by(
        NamespaceInventory.cluster_id.asc(),
        NamespaceInventory.namespace.asc(),
    ).all()
    namespace_options: dict[str, list[str]] = {}
    for item in namespaces:
        namespace_options.setdefault(item.cluster_id, []).append(item.namespace)
    return {
        'clusters': clusters,
        'namespace_options': namespace_options,
        'secret_types': SECRET_TYPE_LABELS,
    }


def _required(value: str | None, label: str) -> str:
    normalized = (value or '').strip()
    if not normalized:
        raise ValueError(f'{label} is required.')
    return normalized


def _build_string_data(form: Any, files: Any, secret_type: str) -> tuple[dict[str, str], dict[str, Any]]:
    metadata: dict[str, Any] = {}
    if secret_type == 'opaque':
        keys = form.getlist('generic_key')
        values = form.getlist('generic_value')
        string_data: dict[str, str] = {}
        for key, value in zip(keys, values, strict=False):
            normalized_key = key.strip()
            if not normalized_key:
                continue
            if normalized_key in string_data:
                raise ValueError(f'Duplicate key: {normalized_key}')
            string_data[normalized_key] = value
        if not string_data:
            raise ValueError('Add at least one key-value entry.')
        metadata['key_names'] = sorted(string_data)
        return string_data, metadata

    if secret_type == 'basic-auth':
        username = _required(form.get('username'), 'Username')
        password = _required(form.get('password'), 'Password')
        if password != (form.get('password_confirm') or ''):
            raise ValueError('Password confirmation does not match.')
        metadata['key_names'] = ['username', 'password']
        return {'username': username, 'password': password}, metadata

    if secret_type == 'tls':
        cert_file = files.get('tls_crt_file')
        key_file = files.get('tls_key_file')
        if cert_file is None or not cert_file.filename:
            raise ValueError('Certificate file is required.')
        if key_file is None or not key_file.filename:
            raise ValueError('Private key file is required.')
        cert_bytes = cert_file.read()
        key_bytes = key_file.read()
        validation = validate_certificate_pair(cert_bytes, key_bytes)
        if not validation.is_valid:
            raise ValueError(' '.join(validation.errors) or 'Certificate and private key do not match.')
        parsed = validation.parsed_certificate
        metadata.update({
            'key_names': ['tls.crt', 'tls.key'],
            'certificate_common_name': getattr(parsed, 'common_name', None),
            'certificate_expiry': parsed.not_after.isoformat() if parsed else None,
            'certificate_fingerprint_sha256': getattr(parsed, 'fingerprint_sha256', None),
        })
        return {
            'tls.crt': cert_bytes.decode('utf-8'),
            'tls.key': key_bytes.decode('utf-8'),
        }, metadata

    if secret_type == 'dockerconfigjson':
        server = _required(form.get('registry_server'), 'Registry server')
        username = _required(form.get('registry_username'), 'Registry username')
        password = _required(form.get('registry_password'), 'Registry password or token')
        email = (form.get('registry_email') or '').strip()
        import base64
        auth = base64.b64encode(f'{username}:{password}'.encode()).decode()
        payload = {'auths': {server: {'username': username, 'password': password, 'auth': auth}}}
        if email:
            payload['auths'][server]['email'] = email
        metadata['key_names'] = ['.dockerconfigjson']
        metadata['registry_server'] = server
        return {'.dockerconfigjson': json.dumps(payload, separators=(',', ':'))}, metadata

    if secret_type == 'ssh-auth':
        key_file = files.get('ssh_private_key_file')
        raw_key = key_file.read().decode('utf-8') if key_file and key_file.filename else (form.get('ssh_private_key') or '')
        if 'PRIVATE KEY' not in raw_key:
            raise ValueError('A valid PEM/OpenSSH private key is required.')
        metadata['key_names'] = ['ssh-privatekey']
        return {'ssh-privatekey': raw_key}, metadata

    raise ValueError('Unsupported Secret type.')


def execute_secret_operation(form: Any, files: Any, *, dry_run: bool) -> SecretOperationResult:
    cluster_id = _required(form.get('cluster_id'), 'Cluster')
    namespace = _required(form.get('namespace'), 'Namespace')
    name = _required(form.get('secret_name'), 'Secret name')
    secret_type = _required(form.get('secret_type'), 'Secret type')
    cluster = Cluster.query.filter_by(id=cluster_id).first()
    if cluster is None:
        raise ValueError('Selected cluster was not found.')

    string_data, safe_metadata = _build_string_data(form, files, secret_type)
    body = V1Secret(
        api_version='v1',
        kind='Secret',
        metadata=V1ObjectMeta(name=name, namespace=namespace),
        immutable=form.get('immutable') == 'true',
        string_data=string_data,
        type=SECRET_KUBERNETES_TYPES[secret_type],
    )
    try:
        with legacy_tls_context(enabled=bool(cluster.kube_allow_weak_tls)):
            api = KubernetesClient(cluster.kubeconfig, verify_ssl=bool(cluster.kube_verify_ssl)).core_api()
            created = api.create_namespaced_secret(
                namespace=namespace,
                body=body,
                dry_run='All' if dry_run else None,
            )
    except ApiException as exc:
        reason = getattr(exc, 'reason', None) or 'Kubernetes API rejected the Secret.'
        if getattr(exc, 'status', None) == 409:
            reason = 'A Secret with this name already exists. Existing data was not changed.'
        raise ValueError(reason) from exc

    operation = 'validation' if dry_run else 'creation'
    return SecretOperationResult(
        status='success',
        title=f'Secret {operation} completed',
        message=(
            f'{name} is valid and ready to create in {cluster.name}/{namespace}.'
            if dry_run else f'{name} was created in {cluster.name}/{namespace}.'
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
            **safe_metadata,
        },
    )
