from __future__ import annotations

from typing import Literal

TLSJobTerminalStatus = Literal['succeeded', 'partially_succeeded', 'failed']


def classify_tls_sync_outcome(
    *,
    target_count: int,
    failed_count: int,
    warning_count: int = 0,
) -> TLSJobTerminalStatus:
    """Classify one fleet TLS sync without depending on Flask, SQLAlchemy, or Celery."""
    targets = max(int(target_count), 0)
    failures = min(max(int(failed_count), 0), targets)
    warnings = min(max(int(warning_count), 0), max(targets - failures, 0))
    if targets and failures == targets:
        return 'failed'
    if failures or warnings:
        return 'partially_succeeded'
    return 'succeeded'
