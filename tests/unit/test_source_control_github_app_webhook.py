"""GitHub webhook authenticity and installation-scope negative contracts (#2741)."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from app.integrations.source_control.source_control.providers.github.webhook import (
    GitHubWebhookError,
    verify_webhook,
)

DELIVERY = '6d670ec2-5de8-11e8-bc12-18b6d4a166f7'
SECRET = "It's a Secret to Everybody"


def _headers(payload: bytes, *, event: str = 'workflow_run') -> dict[str, str]:
    digest = hmac.new(SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return {
        'X-Hub-Signature-256': 'sha256=' + digest,
        'X-GitHub-Delivery': DELIVERY,
        'X-GitHub-Event': event,
        'Content-Type': 'application/json',
    }


def _body(installation: int = 7, repository: int = 35) -> bytes:
    return json.dumps({
        'installation': {'id': installation},
        'repository': {'id': repository},
        'action': 'completed',
        'workflow_run': {'id': 123, 'conclusion': 'failure'},
    }).encode()


def test_verified_delivery_has_only_safe_transport_identity() -> None:
    payload = _body()
    verified = verify_webhook(
        payload=payload, headers=_headers(payload),
        webhook_secret=SECRET, expected_installation_id=7,
    )
    assert verified.installation_id == 7
    assert verified.repository_id == 35
    assert verified.event == 'workflow_run'
    assert verified.action == 'completed'
    assert verified.delivery_id == DELIVERY
    assert not hasattr(verified, 'workflow_run')


def test_official_github_signature_test_vector() -> None:
    body = b'Hello, World!'
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    assert digest == '757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17'


@pytest.mark.parametrize('bad_signature', [
    '',
    'sha1=' + 'a' * 40,
    'sha256=' + 'a' * 64,
    'sha256=' + 'g' * 64,
    'sha256=' + 'a' * 63,
])
def test_unauthorized_signature_never_admitted(bad_signature: str) -> None:
    payload = _body()
    headers = _headers(payload)
    headers['X-Hub-Signature-256'] = bad_signature
    with pytest.raises(GitHubWebhookError):
        verify_webhook(
            payload=payload, headers=headers, webhook_secret=SECRET, expected_installation_id=7
        )


def test_payload_tampering_is_rejected() -> None:
    payload = _body()
    headers = _headers(payload)
    with pytest.raises(GitHubWebhookError):
        verify_webhook(
            payload=_body(installation=8), headers=headers,
            webhook_secret=SECRET, expected_installation_id=7,
        )


def test_valid_signature_from_other_installation_is_rejected() -> None:
    payload = _body(installation=9)
    with pytest.raises(GitHubWebhookError, match='does not match'):
        verify_webhook(
            payload=payload, headers=_headers(payload),
            webhook_secret=SECRET, expected_installation_id=7,
        )


def test_unsupported_event_and_invalid_delivery_are_rejected() -> None:
    payload = _body()
    unsupported = _headers(payload, event='unknown')
    with pytest.raises(GitHubWebhookError, match='not admitted'):
        verify_webhook(
            payload=payload, headers=unsupported,
            webhook_secret=SECRET, expected_installation_id=7,
        )
    malformed = _headers(payload)
    malformed['X-GitHub-Delivery'] = '../../path'
    with pytest.raises(GitHubWebhookError, match='delivery identity'):
        verify_webhook(
            payload=payload, headers=malformed,
            webhook_secret=SECRET, expected_installation_id=7,
        )


def test_large_payload_rejected_before_hmac_or_json() -> None:
    payload = b'A' * 262_145
    with pytest.raises(GitHubWebhookError, match='size limit'):
        verify_webhook(
            payload=payload, headers=_headers(payload),
            webhook_secret=SECRET, expected_installation_id=7,
        )


def test_no_webhook_route_or_producer_is_exposed_by_pure_transport() -> None:
    from pathlib import Path

    project = Path(__file__).resolve().parents[2]
    source = (project / 'app/integrations/source_control/source_control/providers/github/webhook.py').read_text()
    assert 'Blueprint(' not in source
    assert 'JobExecution' not in source
    assert 'db.session' not in source
