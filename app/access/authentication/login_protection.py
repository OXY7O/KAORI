"""Shared bounded identity request budget; separate from confirmed password failures."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from ipaddress import IPv6Address, ip_address
from urllib.parse import urlsplit

from flask import current_app, request
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
ORIGIN_REQUEST_LIMIT = 3  # Candidate opt-in cap, separately qualified before activation.
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
    origin_over_budget: bool = False

    @property
    def blocked(self) -> bool:
        return self.mode == LockoutMode.ENFORCED and (self.over_budget or self.origin_over_budget)


def identity_bucket(username: str, secret: str | bytes) -> str:
    key = secret.encode() if isinstance(secret, str) else secret
    digest = hmac.digest(key, b'kaori:login-identity:v1:' + username.strip().casefold().encode(), hashlib.sha256)
    bucket = int.from_bytes(digest[:4], 'big') % BUCKET_COUNT
    namespace = hmac.digest(key, b'kaori:login-identity:namespace:v1', hashlib.sha256).hex()[:24]
    return f'kaori:login-identity:v1:{namespace}:{bucket:05x}'


def origin_identity_bucket(username: str, origin: str | None, secret: str | bytes) -> str:
    """Uniform, privacy-safe effective origin/identity pair, not user identity proof."""
    if not isinstance(origin, str) or not origin or '%' in origin:
        raise LoginProtectionUnavailable('Shared login protection origin is unavailable.')
    try:
        address = ip_address(origin)
    except ValueError as exc:
        raise LoginProtectionUnavailable('Shared login protection origin is unavailable.') from exc
    # Normalize IPv4-mapped IPv6 to the same origin representation.
    if isinstance(address, IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    key = secret.encode() if isinstance(secret, str) else secret
    namespace = hmac.digest(key, b'kaori:login-origin-identity:namespace:v1', hashlib.sha256).hex()[:24]
    payload = b'kaori:login-origin-identity:v1:' + str(address).encode() + b'\x00'
    payload += username.strip().casefold().encode()
    digest = hmac.digest(key, payload, hashlib.sha256)
    bucket = int.from_bytes(digest[:4], 'big') % BUCKET_COUNT
    return f'kaori:login-origin-identity:v1:{namespace}:{bucket:05x}'


def _shared_storage_configuration() -> tuple[str, str | bytes]:
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
        return uri, secret
    except (ValueError, TypeError) as exc:
        raise LoginProtectionUnavailable('Shared login protection is unavailable.') from exc


def _shared_budget(uri: str, bucket: str, *, limit: int) -> bool:
    try:
        with Redis.from_url(uri, socket_connect_timeout=2, socket_timeout=2) as client:
            count = client.eval(_INCREMENT, 1, bucket, WINDOW_SECONDS, limit)
        if type(count) is not int or not 1 <= count <= limit + 1:
            raise LoginProtectionUnavailable('Shared login protection returned an invalid result.')
        return count > limit
    except (RedisError, ValueError, TypeError, OSError) as exc:
        raise LoginProtectionUnavailable('Shared login protection is unavailable.') from exc


def shared_identity_budget(username: str) -> bool:
    """Return whether this request exceeds its finite shared identity budget."""
    uri, secret = _shared_storage_configuration()
    return _shared_budget(uri, identity_bucket(username, secret), limit=REQUEST_LIMIT)


def shared_origin_identity_budget(username: str, origin: str | None) -> bool:
    """Apply the same additional budget to all identities, including unknown ones."""
    uri, secret = _shared_storage_configuration()
    return _shared_budget(uri, origin_identity_bucket(username, origin, secret), limit=ORIGIN_REQUEST_LIMIT)


def probe_shared_login_protection() -> None:
    """Exercise the exact Redis script in separate expiring deployment probe buckets."""
    uri, secret = _shared_storage_configuration()
    probe_key = identity_bucket('', secret).rsplit(':', 1)[0] + ':qualification-probe'
    _shared_budget(uri, probe_key, limit=REQUEST_LIMIT)
    if current_app.config.get('AUTH_LOGIN_ORIGIN_BUDGET_ENABLED'):
        origin_probe = origin_identity_bucket('', '127.0.0.1', secret).rsplit(':', 1)[0] + ':qualification-probe'
        _shared_budget(uri, origin_probe, limit=ORIGIN_REQUEST_LIMIT)


def read_login_policy(*, lock: bool = False) -> tuple[LockoutMode, int]:
    statement = select(
        AuthenticationSecurityPolicy.lockout_mode, AuthenticationSecurityPolicy.lockout_revision
    ).where(AuthenticationSecurityPolicy.id == 1)
    if lock:
        statement = statement.with_for_update(read=True, of=AuthenticationSecurityPolicy)
    row = db.session.execute(statement).one_or_none()
    mode = LockoutMode(row[0]) if row is not None else LockoutMode.DISABLED
    revision = int(row[1]) if row is not None else 1
    if revision < 1:
        raise LoginProtectionUnavailable('Invalid login protection policy.')
    return mode, revision


def check_login_request(username: str) -> LoginRequestProtection:
    """Read only the mode/revision before any identity lookup or provider call."""
    mode, revision = read_login_policy()
    # No additional request budget is activated implicitly in Disabled.
    if mode == LockoutMode.DISABLED:
        return LoginRequestProtection(mode, revision)
    identity_over = shared_identity_budget(username)
    origin_over = False
    if current_app.config.get('AUTH_LOGIN_ORIGIN_BUDGET_ENABLED'):
        # The existing trusted proxy boundary owns remote_addr. Never read
        # arbitrary forwarded headers or look up an account to choose a budget.
        origin_over = shared_origin_identity_budget(username, request.remote_addr)
    return LoginRequestProtection(mode, revision, identity_over or origin_over, origin_over)
