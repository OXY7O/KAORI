from __future__ import annotations

import base64
import json
from typing import Any

from kubernetes.client import V1ObjectMeta, V1Secret
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException
from urllib3.exceptions import HTTPError as Urllib3HTTPError

from app.common.kubernetes_secrets import scrub_secret_payload
from app.common.sensitive_uploads import decode_utf8
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.resolver import (
    tls_policy_for_cluster,
)
from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.tls import weak_tls_context
from app.kubernetes.governance.tls_certificates.certificate import validate_certificate_pair
from app.kubernetes.operations.secrets.contracts import SecretOperationResult
from app.kubernetes.operations.secrets.live_service import core_api, get_cluster, verify_live_namespace
from app.kubernetes.operations.secrets.validation import (
    read_required_upload,
    required,
    validate_data_key,
    validate_namespace_name,
    validate_optional_email,
    validate_registry_server,
    validate_secret_name,
    validate_secret_size,
    validate_ssh_private_key,
)
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
            validate_data_key(normalized_key)
            if normalized_key in string_data:
                raise ValueError(f'Duplicate Secret data key: {normalized_key}.')
            string_data[normalized_key] = value
        if not string_data:
            raise ValueError('Add at least one key-value entry.')
        metadata['key_names'] = sorted(string_data)
        validate_secret_size(string_data)
        return string_data, metadata

    if secret_type == 'basic-auth':
        username = required(form.get('username'), 'Username')
        password = required(form.get('password'), 'Password')
        if password != (form.get('password_confirm') or ''):
            raise ValueError('Password confirmation does not match.')
        string_data = {'username': username, 'password': password}
        metadata['key_names'] = ['username', 'password']
        validate_secret_size(string_data)
        return string_data, metadata

    if secret_type == 'tls':
        cert_bytes = read_required_upload(files.get('tls_crt_file'), 'Certificate file')
        key_bytes = read_required_upload(files.get('tls_key_file'), 'Private key file')
        validation = validate_certificate_pair(cert_bytes, key_bytes)
        if not validation.is_valid:
            raise ValueError(' '.join(validation.errors) or 'Certificate and private key do not match.')
        parsed = validation.parsed_certificate
        string_data = {
            'tls.crt': decode_utf8(cert_bytes, 'Certificate file'),
            'tls.key': decode_utf8(key_bytes, 'Private key file'),
        }
        metadata.update(
            {
                'key_names': ['tls.crt', 'tls.key'],
                'certificate_common_name': getattr(parsed, 'common_name', None),
                'certificate_expiry': parsed.not_after.isoformat() if parsed else None,
                'certificate_fingerprint_sha256': getattr(parsed, 'fingerprint_sha256', None),
            }
        )
        validate_secret_size(string_data)
        return string_data, metadata

    if secret_type == 'dockerconfigjson':
        server = required(form.get('registry_server'), 'Registry server')
        username = required(form.get('registry_username'), 'Registry username')
        password = required(form.get('registry_password'), 'Registry password or token')
        email = (form.get('registry_email') or '').strip()
        validate_registry_server(server)
        validate_optional_email(email)

        auth = base64.b64encode(f'{username}:{password}'.encode()).decode()
        payload = {'auths': {server: {'username': username, 'password': password, 'auth': auth}}}
        if email:
            payload['auths'][server]['email'] = email
        string_data = {'.dockerconfigjson': json.dumps(payload, separators=(',', ':'))}
        metadata['key_names'] = ['.dockerconfigjson']
        metadata['registry_server'] = server
        validate_secret_size(string_data)
        return string_data, metadata

    if secret_type == 'ssh-auth':
        key_file = files.get('ssh_private_key_file')
        if key_file is not None and getattr(key_file, 'filename', ''):
            raw_key = decode_utf8(read_required_upload(key_file, 'SSH private key file'), 'SSH private key file')
        else:
            raw_key = required(form.get('ssh_private_key'), 'SSH private key')
        validate_ssh_private_key(raw_key)
        string_data = {'ssh-privatekey': raw_key}
        metadata['key_names'] = ['ssh-privatekey']
        validate_secret_size(string_data)
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
    cluster_id = required(form.get('cluster_id'), 'Cluster')
    namespace = required(form.get('namespace'), 'Namespace')
    name = required(form.get('secret_name'), 'Secret name')
    secret_type = required(form.get('secret_type'), 'Secret type')
    immutable_value = (form.get('immutable') or 'false').strip().lower()

    if secret_type not in SECRET_KUBERNETES_TYPES:
        raise ValueError('Unsupported Secret type.')
    if immutable_value not in {'true', 'false'}:
        raise ValueError('Mutability selection is invalid.')

    validate_secret_name(name)
    validate_namespace_name(namespace)

    cluster = get_cluster(cluster_id)
    verify_live_namespace(cluster, namespace)

    string_data, safe_metadata = _build_string_data(form, files, secret_type)
    body = V1Secret(
        api_version='v1',
        kind='Secret',
        metadata=V1ObjectMeta(name=name, namespace=namespace),
        immutable=immutable_value == 'true',
        string_data=string_data,
        type=SECRET_KUBERNETES_TYPES[secret_type],
    )

    created = None
    created_uid = None
    created_resource_version = None
    try:
        with weak_tls_context(enabled=tls_policy_for_cluster(cluster)[1]):
            api = core_api(cluster)
            created = api.create_namespaced_secret(
                namespace=namespace,
                body=body,
                dry_run='All' if dry_run else None,
                _request_timeout=10,
            )
            created_metadata = getattr(created, 'metadata', None)
            created_uid = getattr(created_metadata, 'uid', None)
            created_resource_version = getattr(created_metadata, 'resource_version', None)
    except ApiException as exc:
        raise ValueError(_kubernetes_api_error_message(exc)) from exc
    except ConfigException as exc:
        raise ValueError('The selected cluster kubeconfig is invalid or incomplete.') from exc
    except (OSError, Urllib3HTTPError) as exc:
        raise ValueError(
            'KAORI could not reach the Kubernetes API for the selected cluster. '
            'Check connectivity and cluster configuration.'
        ) from exc
    finally:
        for key in list(string_data):
            string_data[key] = ''
        string_data.clear()
        body.string_data = None
        scrub_secret_payload(created)

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
            'live_target_source': True,
            'inventory_target_gate': False,
            'resource_uid': created_uid,
            'resource_version': created_resource_version,
            **safe_metadata,
        },
    )
