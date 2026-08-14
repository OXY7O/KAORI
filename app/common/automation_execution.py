from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from flask import current_app, has_app_context

EXECUTION_CONFIG_KEY = 'AUTOMATION_EXECUTION_ENABLED'


class ResolverExecutionDisabled(RuntimeError):
    """Raised when a request attempts to cross the infrastructure execution boundary while disabled."""


def execution_enabled(config: Mapping[str, object] | None = None) -> bool:
    source = config
    if source is None:
        if not has_app_context():
            return False
        source = current_app.config
    return bool(source.get(EXECUTION_CONFIG_KEY, False))


def assert_execution_enabled(config: Mapping[str, object] | None = None) -> None:
    if not execution_enabled(config):
        raise ResolverExecutionDisabled(
            'Infrastructure execution is disabled by AUTOMATION_EXECUTION_ENABLED. '
            'Governance configuration remains available, but resolver mutation is fail-closed.'
        )


def build_idempotency_key(*, decision_id: str, action_key: str, evidence_hash: str) -> str:
    """Build the cross-domain identity for one immutable decision execution."""
    payload = json.dumps(
        {
            'action_key': action_key,
            'decision_id': decision_id,
            'evidence_hash': evidence_hash,
        },
        sort_keys=True,
        separators=(',', ':'),
    )
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()
