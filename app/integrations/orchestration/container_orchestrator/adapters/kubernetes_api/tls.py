from __future__ import annotations

import ssl
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from urllib3.util.ssl_ import create_urllib3_context


def configure_weak_tls(api_client: Any, *, enabled: bool, verify_ssl: bool) -> None:
    """Scope operator-approved legacy cipher policy to one Kubernetes API transport.

    Kubernetes SDK RESTClientObject owns an urllib3 pool manager per ApiClient.
    Set its TLS context before the first request; never monkey-patch urllib3
    functions, which would weaken unrelated concurrent provider connections.
    The SDK's CA bundle and optional client certificate are still configured on
    that manager and remain authoritative for certificate validation.
    """
    if not enabled:
        return
    manager = getattr(getattr(api_client, 'rest_client', None), 'pool_manager', None)
    pool_options = getattr(manager, 'connection_pool_kw', None)
    if not isinstance(pool_options, dict):
        raise RuntimeError('Kubernetes client cannot scope legacy TLS to this transport.')

    context = create_urllib3_context(
        ciphers='DEFAULT:@SECLEVEL=0',
        cert_reqs=ssl.CERT_REQUIRED if verify_ssl else ssl.CERT_NONE,
    )
    if not verify_ssl:
        context.check_hostname = False
    pool_options['ssl_context'] = context


@contextmanager
def weak_tls_context(*, enabled: bool) -> Iterator[None]:
    """Temporary import-compatibility bridge for pre-migration callers.

    Legacy TLS is owned by KubernetesClient's per-transport configuration.
    This deliberately never patches urllib3 process globals or relaxes TLS.
    The `enabled` flag cannot change TLS for a client built outside the
    canonical adapter; such callers must migrate to Kubernetes client.build.
    Do not use this compatibility bridge for new provider operations.
    """
    yield
