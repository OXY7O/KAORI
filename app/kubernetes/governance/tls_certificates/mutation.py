from __future__ import annotations

import base64
from typing import Any

from app.common.kubernetes_secrets import scrub_mapping_values, scrub_secret_payload
from app.common.sensitive_uploads import read_required_upload_bytes
from app.extensions.db import db
from app.kubernetes.governance.tls_certificates.collector import build_kubernetes_client
from app.kubernetes.governance.tls_certificates.constants import TLS_CRT_KEY, TLS_KEY_KEY, TLS_SECRET_TYPE
from app.models import Cluster


def read_uploaded_pair(files: Any) -> tuple[bytes, bytes]:
    return (
        read_required_upload_bytes(
            files.get('tls_crt_file') or files.get('tls_crt'),
            'Certificate file',
        ),
        read_required_upload_bytes(
            files.get('tls_key_file') or files.get('tls_key'),
            'Private key file',
        ),
    )


def patch_tls_secret(record: Any, cert_bytes: bytes, key_bytes: bytes) -> str:
    cluster = db.session.get(Cluster, record.cluster_id)
    if cluster is None:
        raise ValueError('Cluster record no longer exists.')

    api = build_kubernetes_client(cluster).core_api()
    live_secret = api.read_namespaced_secret(
        name=record.secret_name,
        namespace=record.namespace,
        _request_timeout=10,
    )
    try:
        secret_type = str(getattr(live_secret, 'type', None) or '')
        metadata = getattr(live_secret, 'metadata', None)
        resource_version = str(getattr(metadata, 'resource_version', None) or '')
    finally:
        scrub_secret_payload(live_secret)

    if secret_type != TLS_SECRET_TYPE:
        raise ValueError('The live Kubernetes Secret is no longer a TLS Secret.')
    if not resource_version:
        raise ValueError('Kubernetes did not return a Secret resource version. Refresh TLS inventory and retry.')

    encoded_data = {
        TLS_CRT_KEY: base64.b64encode(cert_bytes).decode('ascii'),
        TLS_KEY_KEY: base64.b64encode(key_bytes).decode('ascii'),
    }
    body = {
        'metadata': {'resourceVersion': resource_version},
        'type': TLS_SECRET_TYPE,
        'data': encoded_data,
    }
    try:
        for dry_run in ('All', None):
            response = api.patch_namespaced_secret(
                name=record.secret_name,
                namespace=record.namespace,
                body=body,
                dry_run=dry_run,
                field_manager='kaori-tls-secret-rotation',
                _request_timeout=10,
            )
            scrub_secret_payload(response)
    finally:
        scrub_mapping_values(encoded_data)
        body['data'] = None

    return resource_version
