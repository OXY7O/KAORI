from __future__ import annotations

from typing import Literal

TLSJobTerminalStatus = Literal['succeeded', 'partially_succeeded', 'failed']


def classify_tls_sync_outcome(*, target_count: int, failed_count: int) -> TLSJobTerminalStatus:
    """Classify one fleet TLS sync without depending on Flask, SQLAlchemy, or Celery."""
    targets = max(int(target_count), 0)
    failures = min(max(int(failed_count), 0), targets)
    if targets and failures == targets:
        return 'failed'
    if failures:
        return 'partially_succeeded'
    return 'succeeded'
