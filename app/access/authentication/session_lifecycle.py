"""Server-owned human web session lifecycle, bound to the existing login generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import case, select, update

from app.access.authentication.audit import stage_session_expiry
from app.extensions.db import db
from app.models.authentication_security import AuthenticationSecurityPolicy
from app.models.user import User

ExpiryReason = Literal['session_state_invalid', 'absolute_timeout', 'idle_timeout']


@dataclass(frozen=True, slots=True)
class SessionPolicy:
    privileged_idle_minutes: int = 15
    privileged_absolute_hours: int = 4
    regular_idle_minutes: int = 30
    regular_absolute_hours: int = 8
    warning_minutes: int = 2
    regular_remember: bool = True

    def __post_init__(self) -> None:
        if not 5 <= self.privileged_idle_minutes <= self.regular_idle_minutes <= 60:
            raise ValueError('Invalid idle session policy.')
        if not 1 <= self.privileged_absolute_hours <= self.regular_absolute_hours <= 24:
            raise ValueError('Invalid absolute session policy.')
        if not 1 <= self.warning_minutes <= 5 or self.warning_minutes >= self.privileged_idle_minutes:
            raise ValueError('Invalid session warning policy.')

    def limits(self, *, privileged: bool) -> tuple[timedelta, timedelta]:
        if privileged:
            return timedelta(minutes=self.privileged_idle_minutes), timedelta(hours=self.privileged_absolute_hours)
        return timedelta(minutes=self.regular_idle_minutes), timedelta(hours=self.regular_absolute_hours)


def read_session_policy() -> SessionPolicy:
    # Select only session fields, never decrypt unrelated Bot Protection secrets
    # on the authenticated request path.
    row = db.session.execute(
        select(
            AuthenticationSecurityPolicy.session_privileged_idle_minutes,
            AuthenticationSecurityPolicy.session_privileged_absolute_hours,
            AuthenticationSecurityPolicy.session_regular_idle_minutes,
            AuthenticationSecurityPolicy.session_regular_absolute_hours,
            AuthenticationSecurityPolicy.session_warning_minutes,
            AuthenticationSecurityPolicy.session_regular_remember,
        ).where(AuthenticationSecurityPolicy.id == 1)
    ).one_or_none()
    return SessionPolicy(*row) if row is not None else SessionPolicy()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class SessionDeadlines:
    idle: datetime
    absolute: datetime

    def payload(self, now: datetime, policy: SessionPolicy) -> dict[str, int]:
        return {
            'idle_remaining_seconds': max(0, int((self.idle - now).total_seconds())),
            'absolute_remaining_seconds': max(0, int((self.absolute - now).total_seconds())),
            'warning_seconds': policy.warning_minutes * 60,
        }


def session_deadlines(user: User, policy: SessionPolicy, now: datetime) -> SessionDeadlines | ExpiryReason:
    issued, activity = user.auth_session_issued_at, user.auth_session_activity_at
    if issued is None or activity is None:
        return 'session_state_invalid'
    issued, activity = _utc(issued), _utc(activity)
    # Small clock differences between synchronized web instances must not
    # accidentally strand an otherwise valid newly issued session.
    if activity < issued or activity > now + timedelta(seconds=5) or issued > now + timedelta(seconds=5):
        return 'session_state_invalid'
    idle_limit, absolute_limit = policy.limits(privileged=user.is_admin_level)
    absolute = issued + absolute_limit
    idle = activity + idle_limit
    if now >= absolute:
        return 'absolute_timeout'
    if now >= idle:
        return 'idle_timeout'
    return SessionDeadlines(idle=idle, absolute=absolute)


def revoke_generation(user_id: int, generation: int, *, expected: User | None = None) -> bool:
    """Stage exact-generation revocation without committing another login's state."""
    conditions = [User.id == user_id, User.auth_session_version == generation]
    if expected is not None:
        # A simultaneous legitimate activity refresh may have won the race.
        # Never revoke a newer or refreshed generation using a stale observation.
        conditions.extend((
            User.auth_session_issued_at == expected.auth_session_issued_at,
            User.auth_session_activity_at == expected.auth_session_activity_at,
        ))
    result = db.session.execute(
        update(User)
        .where(*conditions)
        .values(
            auth_session_version=User.auth_session_version + 1,
            auth_session_issued_at=None,
            auth_session_activity_at=None,
            updated_at=User.updated_at,
        )
        .returning(User.id)
        .execution_options(synchronize_session=False)
    ).scalar_one_or_none()
    return result is not None


def expire_generation(user: User, generation: int, reason: ExpiryReason) -> bool:
    if not revoke_generation(user.id, generation, expected=user):
        db.session.rollback()
        return False
    db.session.add(stage_session_expiry(user, reason=reason))
    db.session.commit()
    return True


def refresh_activity(user: User, generation: int, policy: SessionPolicy, now: datetime) -> bool:
    """Refresh only an admitted generation, never resurrect an expired one."""
    idle_limit, absolute_limit = policy.limits(privileged=user.is_admin_level)
    result = db.session.execute(
        update(User)
        .where(
            User.id == user.id,
            User.auth_session_version == generation,
            User.account_is_active.is_(True),
            User.deleted_at.is_(None),
            User.auth_session_issued_at > now - absolute_limit,
            User.auth_session_activity_at > now - idle_limit,
            User.auth_session_activity_at >= User.auth_session_issued_at,
        )
        .values(
            auth_session_activity_at=case(
                (User.auth_session_activity_at < now, now),
                else_=User.auth_session_activity_at,
            ),
            updated_at=User.updated_at,
        )
        .returning(User.id)
        .execution_options(synchronize_session=False)
    ).scalar_one_or_none()
    if result is None:
        db.session.rollback()
        return False
    db.session.commit()
    return True
