"""Shared bounded identity request budget; separate from confirmed password failures."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from urllib.parse import urlsplit

from flask import current_app
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import select

from app.access.authentication.lockout_policy import LockoutMode
from app.extensions.db import db
from app.models.authentication_security import AuthenticationSecurityPolicy

# Bounded keyed buckets across known and unknown identities. Collisions can
# temporarily throttle unrelated identities; they cannot lock their accounts.
BUCKET_COUNT = 262_144
REQUEST_LIMIT = 30
WINDOW_SECONDS = 60
_INCREMENT = """
local value = redis.call('GET', KEYS[1])
if not value then
    redis.call('SET', KEYS[1], 1, 'EX', ARGV[1])
    return 1
end
local count = tonumber(value)
if not count or count < 1 or redis.call('TTL', KEYS[1]) < 0 then
    return redis.error_reply('invalid login protection bucket')
end
if count >= tonumber(ARGV[2]) + 1 then
    return count
end
return redis.call('INCR', KEYS[1])
"""


class LoginProtectionUnavailable(RuntimeError):
    """Required shared protection cannot be verified."""


@dataclass(frozen=True, slots=True)
class LoginRequestProtection:
    mode: LockoutMode
    revision: int
    over_budget: bool = False

    @property
    def blocked(self) -> bool:
        return self.mode == LockoutMode.ENFORCED and self.over_budget


def identity_bucket(username: str, secret: str | bytes) -> str:
    key = secret.encode() if isinstance(secret, str) else secret
    digest = hmac.digest(key, b'kaori:login-identity:v1:' + username.strip().casefold().encode(), hashlib.sha256)
    bucket = int.from_bytes(digest[:4], 'big') % BUCKET_COUNT
    return f'kaori:login-identity:v1:{bucket:05x}'


def shared_identity_budget(username: str) -> bool:
    """Return whether this request exceeds its finite shared identity budget."""
    config = current_app.config
    uri = config.get('RATELIMIT_STORAGE_URI')
    secret = config.get('SECRET_KEY')
    try:
        if (
            not config.get('RATELIMIT_ENABLED')
            or config.get('RATELIMIT_SWALLOW_ERRORS')
            or config.get('RATELIMIT_IN_MEMORY_FALLBACK_ENABLED')
            or config.get('RATELIMIT_IN_MEMORY_FALLBACK')
            or not isinstance(uri, str)
            or urlsplit(uri).scheme not in {'redis', 'rediss'}
            or not isinstance(secret, (str, bytes))
            or len(secret) < 16
            or secret in ('change-me', b'change-me')
        ):
            raise LoginProtectionUnavailable('Shared login protection is unavailable.')
        with Redis.from_url(uri, socket_connect_timeout=2, socket_timeout=2) as client:
            count = client.eval(_INCREMENT, 1, identity_bucket(username, secret), WINDOW_SECONDS, REQUEST_LIMIT)
        if type(count) is not int or not 1 <= count <= REQUEST_LIMIT + 1:
            raise LoginProtectionUnavailable('Shared login protection returned an invalid result.')
        return count > REQUEST_LIMIT
    except (RedisError, ValueError, TypeError, OSError) as exc:
        raise LoginProtectionUnavailable('Shared login protection is unavailable.') from exc


def check_login_request(username: str) -> LoginRequestProtection:
    """Read only the mode/revision before any identity lookup or provider call."""
    row = db.session.execute(
        select(AuthenticationSecurityPolicy.lockout_mode, AuthenticationSecurityPolicy.lockout_revision)
        .where(AuthenticationSecurityPolicy.id == 1)
    ).one_or_none()
    mode = LockoutMode(row[0]) if row is not None else LockoutMode.DISABLED
    revision = int(row[1]) if row is not None else 1
    if revision < 1:
        raise LoginProtectionUnavailable('Invalid login protection policy.')
    # No new request budget is activated implicitly in Disabled.
    return LoginRequestProtection(
        mode, revision, shared_identity_budget(username) if mode != LockoutMode.DISABLED else False
    )
