"""Pure bounded local password lockout policy from #4015."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

WINDOW = timedelta(minutes=15)
LOCK_DURATION = timedelta(minutes=15)
FAILURE_LIMIT = 10


class LockoutMode(StrEnum):
    DISABLED = 'disabled'
    MONITOR_ONLY = 'monitor_only'
    ENFORCED = 'enforced'


class LockoutGate(StrEnum):
    OPEN = 'open'
    COOLDOWN = 'cooldown'
    LOCKED = 'locked'


@dataclass(frozen=True, slots=True)
class LockoutState:
    failures: tuple[datetime, ...] = ()
    cooldown_until: datetime | None = None
    locked_until: datetime | None = None


@dataclass(frozen=True, slots=True)
class LockoutDecision:
    mode: LockoutMode
    state: LockoutState
    gate: LockoutGate
    auto_unlocked: bool = False

    @property
    def blocked(self) -> bool:
        return self.mode == LockoutMode.ENFORCED and self.gate != LockoutGate.OPEN


def utc(value: datetime) -> datetime:
    # SQLite returns naive UTC for timezone-aware columns in contract tests.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def inspect_state(mode: LockoutMode, state: LockoutState, *, now: datetime) -> LockoutDecision:
    if mode == LockoutMode.DISABLED:
        return LockoutDecision(mode, LockoutState(), LockoutGate.OPEN)
    now = utc(now)
    failures = tuple(utc(item) for item in state.failures)
    cooldown = utc(state.cooldown_until) if state.cooldown_until is not None else None
    locked = utc(state.locked_until) if state.locked_until is not None else None
    if (
        len(failures) > FAILURE_LIMIT
        or failures != tuple(sorted(failures))
        or any(item > now for item in failures)
        or (locked is not None and (len(failures) != FAILURE_LIMIT or cooldown is not None))
        or (locked is None and len(failures) == FAILURE_LIMIT)
        or (cooldown is not None and len(failures) < 3)
        or (locked is not None and locked != failures[-1] + LOCK_DURATION)
        or (cooldown is not None and cooldown != failures[-1] + timedelta(seconds=5 if len(failures) < 5 else 30))
    ):
        raise ValueError('Invalid committed account lockout state.')
    if locked is not None:
        if locked > now:
            return LockoutDecision(mode, LockoutState(failures, locked_until=locked), LockoutGate.LOCKED)
        return LockoutDecision(mode, LockoutState(), LockoutGate.OPEN, auto_unlocked=True)
    recent = tuple(item for item in failures if now - WINDOW < item)
    if cooldown is not None and cooldown > now:
        # A rolling-window boundary may remove older failures while the already
        # committed cooldown remains active. Keep its original bounded window
        # until expiry, then prune before the next qualifying failure.
        return LockoutDecision(mode, LockoutState(failures, cooldown_until=cooldown), LockoutGate.COOLDOWN)
    return LockoutDecision(mode, LockoutState(recent), LockoutGate.OPEN)


def apply_outcome(
    decision: LockoutDecision, *, password_valid: bool | None, now: datetime
) -> LockoutState:
    """None is a gate-only observation, not a completed password check."""
    if password_valid is not None and type(password_valid) is not bool:
        raise ValueError('Password outcome requires trusted boolean evidence.')
    if decision.mode == LockoutMode.DISABLED:
        return LockoutState()
    if decision.blocked and password_valid is not None:
        raise ValueError('Password verification is not permitted through an enforced gate.')
    if password_valid is True:
        return LockoutState()
    if password_valid is None or decision.gate != LockoutGate.OPEN:
        return decision.state
    now = utc(now)
    failures = tuple(item for item in decision.state.failures if now - WINDOW < item) + (now,)
    if len(failures) == FAILURE_LIMIT:
        return LockoutState(failures, locked_until=now + LOCK_DURATION)
    cooldown = None
    if len(failures) >= 3:
        cooldown = now + timedelta(seconds=5 if len(failures) < 5 else 30)
    return LockoutState(failures, cooldown_until=cooldown)
