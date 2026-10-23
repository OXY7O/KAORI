"""Pure, side-effect-free GitHub App webhook admission contract (#2741).

This module does NOT expose a Flask route or enqueue jobs. Durable deduplication,
App/installation lookup and authorized targeted refresh belong to the later
bounded ingress integration before any webhook endpoint is enabled.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Mapping
from uuid import UUID

_MAX_WEBHOOK_BYTES = 262_144
_SUPPORTED_EVENTS = frozenset({'installation', 'installation_repositories', 'repository', 'workflow_run'})


class GitHubWebhookError(ValueError):
    """Sanitized rejection: never reveal signature, secret or raw request body."""


@dataclass(frozen=True, slots=True)
class VerifiedGitHubDelivery:
    """Verified transport envelope, NOT authoritative committed domain state."""

    delivery_id: str
    event: str
    action: str
    installation_id: int
    repository_id: int | None


def verify_webhook(
    *,
    payload: bytes,
    headers: Mapping[str, str],
    webhook_secret: str,
    expected_installation_id: int,
) -> VerifiedGitHubDelivery:
    """Require trusted raw HMAC-SHA256 and exact installation scope.

    Replay prevention still requires a durable unique provider delivery ID
    claim by the future authenticated ingress owner.
    """
    if not isinstance(payload, bytes) or not payload or len(payload) > _MAX_WEBHOOK_BYTES:
        raise GitHubWebhookError('GitHub webhook body is absent or exceeds the size limit.')
    if not webhook_secret or not isinstance(webhook_secret, str):
        raise GitHubWebhookError('GitHub webhook verification credential is unavailable.')
    signature = str(headers.get('X-Hub-Signature-256') or '')
    if len(signature) != 71 or not signature.startswith('sha256='):
        raise GitHubWebhookError('GitHub webhook signature is missing or invalid.')
    supplied_hex = signature[7:]
    if any(char not in '0123456789abcdef' for char in supplied_hex):
        raise GitHubWebhookError('GitHub webhook signature format is invalid.')
    expected = hmac.new(webhook_secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied_hex):
        raise GitHubWebhookError('GitHub webhook signature verification failed.')
    content_type = str(headers.get('Content-Type') or '').split(';', 1)[0].strip().lower()
    if content_type != 'application/json':
        raise GitHubWebhookError('GitHub webhook content type is unsupported.')
    event = str(headers.get('X-GitHub-Event') or '')
    if event not in _SUPPORTED_EVENTS:
        raise GitHubWebhookError('GitHub webhook event is not admitted.')
    supplied_delivery = str(headers.get('X-GitHub-Delivery') or '')
    try:
        delivery_id = str(UUID(supplied_delivery))
    except (TypeError, ValueError, AttributeError) as exc:
        raise GitHubWebhookError('GitHub webhook delivery identity is invalid.') from exc
    try:
        data = json.loads(payload)
    except (ValueError, UnicodeDecodeError) as exc:
        raise GitHubWebhookError('GitHub webhook payload is invalid.') from exc
    if not isinstance(data, dict):
        raise GitHubWebhookError('GitHub webhook payload must be an object.')
    installation = data.get('installation')
    native_id = installation.get('id') if isinstance(installation, dict) else None
    if isinstance(native_id, bool) or not isinstance(native_id, int) or native_id <= 0:
        raise GitHubWebhookError('GitHub webhook installation identity is missing.')
    if (
        isinstance(expected_installation_id, bool)
        or not isinstance(expected_installation_id, int)
        or expected_installation_id <= 0
        or native_id != expected_installation_id
    ):
        raise GitHubWebhookError('GitHub webhook installation does not match the authorized target.')
    repo = data.get('repository')
    repo_id = repo.get('id') if isinstance(repo, dict) else None
    if repo_id is not None and (isinstance(repo_id, bool) or not isinstance(repo_id, int) or repo_id <= 0):
        raise GitHubWebhookError('GitHub webhook repository identity is invalid.')
    action = data.get('action')
    return VerifiedGitHubDelivery(
        delivery_id=delivery_id,
        event=event,
        action=str(action)[:80] if isinstance(action, str) else '',
        installation_id=native_id,
        repository_id=repo_id,
    )
