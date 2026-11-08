from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.kubernetes.governance.tls_certificates import collector


def page(items, token=''):
    return SimpleNamespace(items=items, metadata=SimpleNamespace(_continue=token))


def secret(name: str, secret_type='kubernetes.io/tls'):
    return SimpleNamespace(
        type=secret_type,
        metadata=SimpleNamespace(namespace='default', name=name),
        data={'tls.crt': 'Y2VydA==', 'tls.key': 'cHJpdmF0ZQ=='},
        string_data={'password': 'hidden'},
    )


def test_tls_collector_scrubs_each_page_and_uses_continuation(monkeypatch):
    calls = []
    first, second, unrelated = secret('a'), secret('b'), secret('not-tls', 'Opaque')

    def list_secrets(**kwargs):
        calls.append(kwargs)
        if len(calls) == 2:
            assert first.data is None
            assert first.string_data is None
            assert unrelated.data is None
            return page([second])
        return page([first, unrelated], 'next-page')

    cluster = SimpleNamespace(name='Example', id='cluster-1')
    client = SimpleNamespace(
        core_api=lambda: SimpleNamespace(list_secret_for_all_namespaces=list_secrets),
    )
    monkeypatch.setattr(collector, 'collect_ingress_tls_usage', lambda cluster: {})
    monkeypatch.setattr(collector, 'build_kubernetes_client', lambda cluster: client)
    monkeypatch.setattr(
        collector,
        'parse_tls_secret',
        lambda item, usage_map, **kwargs: {
            'namespace': item.metadata.namespace,
            'secret_name': item.metadata.name,
        },
    )
    batch = collector.collect_tls_certificate_batch(cluster)
    assert batch.error is None
    assert [item['secret_name'] for item in batch.records] == ['a', 'b']
    assert [call['_continue'] for call in calls] == [None, 'next-page']
    assert all(call['limit'] == 100 and call['_request_timeout'] == 10 for call in calls)
    assert second.data is None and second.string_data is None


@pytest.mark.parametrize(
    'bad_page',
    [
        SimpleNamespace(items=None, metadata=None),
        SimpleNamespace(items={'unexpected': 'mapping'}, metadata=None),
    ],
)
def test_incomplete_secret_listing_fails_closed_and_scrubs(monkeypatch, bad_page):
    cluster = SimpleNamespace(name='Example')
    monkeypatch.setattr(collector, 'collect_ingress_tls_usage', lambda cluster: {})
    monkeypatch.setattr(
        collector,
        'build_kubernetes_client',
        lambda cluster: SimpleNamespace(
            core_api=lambda: SimpleNamespace(list_secret_for_all_namespaces=lambda **kwargs: bad_page),
        ),
    )
    batch = collector.collect_tls_certificate_batch(cluster)
    assert batch.error is not None
    assert batch.records == []
    assert batch.evidence.secret_collection_status == 'collection_failed'


def test_secret_continuation_cycle_fails_without_partial_records(monkeypatch):
    old = secret('a')
    cluster = SimpleNamespace(name='Example')
    monkeypatch.setattr(collector, 'collect_ingress_tls_usage', lambda cluster: {})
    monkeypatch.setattr(
        collector,
        'build_kubernetes_client',
        lambda cluster: SimpleNamespace(
            core_api=lambda: SimpleNamespace(
                list_secret_for_all_namespaces=lambda **kwargs: page([old], 'loop-token'),
            ),
        ),
    )
    monkeypatch.setattr(collector, 'parse_tls_secret', lambda item, mapping, **kwargs: {'secret_name': 'a'})
    batch = collector.collect_tls_certificate_batch(cluster)
    assert batch.error is not None and not batch.records
    assert old.data is None


def test_ingress_pagination_merges_consumer_evidence_across_pages(monkeypatch):
    cluster = SimpleNamespace(name='Example')

    def ingress(name):
        return SimpleNamespace(
            metadata=SimpleNamespace(namespace='default', name=name),
            spec=SimpleNamespace(
                tls=[
                    SimpleNamespace(secret_name='shared', hosts=[f'{name}.example.com']),
                ]
            ),
        )

    calls = []

    def list_ingress(**kwargs):
        calls.append(kwargs)
        return page(
            [ingress('beta')] if kwargs['_continue'] else [ingress('alpha')], '' if kwargs['_continue'] else 'next'
        )

    monkeypatch.setattr(
        collector,
        'build_kubernetes_client',
        lambda cluster: SimpleNamespace(
            networking_api=lambda: SimpleNamespace(list_ingress_for_all_namespaces=list_ingress),
        ),
    )
    mapping = collector.collect_ingress_tls_usage(cluster)
    assert mapping[('default', 'shared')]['ingress_hosts'] == [
        'alpha.example.com',
        'beta.example.com',
    ]
    assert [call['_continue'] for call in calls] == [None, 'next']
    assert all(call['_request_timeout'] == 10 for call in calls)


def test_oversized_secret_page_fails_closed_and_scrubs_all_payloads():
    entries = [secret(f'secret-{i}') for i in range(101)]
    with pytest.raises(ValueError, match='oversized Secret'):
        collector._collect_pages(
            lambda token: page(entries),
            lambda items: None,
            kind='Secret',
            scrub_secrets=True,
        )
    assert all(entry.data is None and entry.string_data is None for entry in entries)


def test_ingress_missing_identity_does_not_claim_complete_mapping(monkeypatch):
    cluster = SimpleNamespace(name='Example')
    invalid = SimpleNamespace(
        metadata=SimpleNamespace(namespace=None, name='missing-namespace'),
        spec=SimpleNamespace(tls=[SimpleNamespace(secret_name='example', hosts=['api.example.com'])]),
    )
    monkeypatch.setattr(
        collector,
        'build_kubernetes_client',
        lambda cluster: SimpleNamespace(
            networking_api=lambda: SimpleNamespace(
                list_ingress_for_all_namespaces=lambda **kwargs: page([invalid]),
            ),
        ),
    )
    with pytest.raises(ValueError, match='without identity'):
        collector.collect_ingress_tls_usage(cluster)
