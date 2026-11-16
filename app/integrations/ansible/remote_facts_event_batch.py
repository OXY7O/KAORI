"""Bounded fail-closed remote facts event batch review (#4799).

This pure projection cannot dispatch a worker, validate credentials, or grant Run.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.integrations.ansible.remote_facts_event_projection import project_remote_facts_event

_MAX_EVENTS = 64


@dataclass(frozen=True, slots=True)
class FactsEventBatchReview:
    state: str
    reason: str
    projected_events: tuple[tuple[str, str, str], ...] = ()
    execution_authorized: bool = False


def review_remote_facts_event_batch(events: object, *, expected_host: str) -> FactsEventBatchReview:
    """Require one unambiguous successful setup event and no contradictory event.

    The projected tuple contains only host, task, status; raw runner payloads are
    deliberately discarded. Successful evidence still requires independent admission.
    """
    blocked = FactsEventBatchReview("blocked", "Remote facts event batch is not admissible")
    if not isinstance(events, (list, tuple)) or not 1 <= len(events) <= _MAX_EVENTS:
        return blocked
    projected: list[tuple[str, str, str]] = []
    for event in events:
        item = project_remote_facts_event(event, expected_host=expected_host)
        if item is None:
            return blocked
        projected.append((item["host"], item["task"], item["status"]))
    # Do not select a prior success if a later event failed or was unreachable.
    # Multiple successes are ambiguous, not independent corroboration.
    if len(projected) != 1 or projected[0][2] != "ok":
        return blocked
    return FactsEventBatchReview(
        "requires_independent_admission",
        "One successful facts event projected; host, worker and JobExecution admission remain required",
        tuple(projected),
    )
