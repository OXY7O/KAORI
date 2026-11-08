from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def test_live_secret_selector_uses_bounded_paging_and_per_page_scrubbing() -> None:
    source = (ROOT / 'app/kubernetes/operations/secrets/live_service.py').read_text()
    listing = source.split('def list_live_secrets(', 1)[1].split('def read_live_secret(', 1)[0]
    assert 'for _ in range(100)' in listing
    assert 'limit=100' in listing
    assert '_continue=continuation' in listing
    assert '_request_timeout=10' in listing
    assert 'seen_tokens.add(continuation)' in listing
    assert 'scrub_secret_payload(item)' in listing
    assert 'finally:' in listing
    assert 'return sorted(options, key=lambda item: item.name)' in listing
    assert 'Too many live Secrets' in listing


def test_namespace_lookups_have_explicit_request_timeout() -> None:
    source = (ROOT / 'app/kubernetes/operations/secrets/live_service.py').read_text()
    assert 'core_api(cluster).list_namespace(_request_timeout=10)' in source
    assert 'core_api(cluster).read_namespace(name=normalized, _request_timeout=10)' in source
    assert 'api.read_namespace(name=namespace, _request_timeout=10)' in source
