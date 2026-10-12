"""Kubernetes legacy TLS must never mutate urllib3 process globals."""

from types import SimpleNamespace

import urllib3.connection
import urllib3.util.ssl_
import pytest

from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.tls import (
    configure_weak_tls,
)


def _api():
    options = {'ca_certs': '/trusted/ca.pem', 'cert_reqs': 'CERT_REQUIRED'}
    manager = SimpleNamespace(connection_pool_kw=options)
    return SimpleNamespace(rest_client=SimpleNamespace(pool_manager=manager))


def test_legacy_tls_is_local_to_the_approved_api_client():
    original = urllib3.util.ssl_.create_urllib3_context
    connection_original = urllib3.connection.create_urllib3_context
    strict = _api()
    legacy = _api()
    configure_weak_tls(strict, enabled=False, verify_ssl=True)
    configure_weak_tls(legacy, enabled=True, verify_ssl=True)
    assert 'ssl_context' not in strict.rest_client.pool_manager.connection_pool_kw
    scoped = legacy.rest_client.pool_manager.connection_pool_kw
    assert scoped['ssl_context'].verify_mode is not None
    assert scoped['ca_certs'] == '/trusted/ca.pem'
    assert urllib3.util.ssl_.create_urllib3_context is original
    assert urllib3.connection.create_urllib3_context is connection_original


def test_legacy_tls_refuses_unscopable_transport_without_global_fallback():
    api = SimpleNamespace(rest_client=SimpleNamespace(pool_manager=object()))
    with pytest.raises(RuntimeError, match='cannot scope'):
        configure_weak_tls(api, enabled=True, verify_ssl=True)


def test_independent_legacy_clients_never_restore_or_change_global_functions():
    original = urllib3.util.ssl_.create_urllib3_context
    one, two = _api(), _api()
    configure_weak_tls(one, enabled=True, verify_ssl=True)
    configure_weak_tls(two, enabled=True, verify_ssl=False)
    assert one.rest_client.pool_manager.connection_pool_kw['ssl_context'] is not (
        two.rest_client.pool_manager.connection_pool_kw['ssl_context']
    )
    assert urllib3.util.ssl_.create_urllib3_context is original


def test_retired_context_import_bridge_never_mutates_process_global_tls():
    from app.integrations.orchestration.container_orchestrator.adapters.kubernetes_api.tls import weak_tls_context

    original = urllib3.util.ssl_.create_urllib3_context
    connection_original = urllib3.connection.create_urllib3_context
    with weak_tls_context(enabled=True):
        assert urllib3.util.ssl_.create_urllib3_context is original
        assert urllib3.connection.create_urllib3_context is connection_original
    assert urllib3.util.ssl_.create_urllib3_context is original
