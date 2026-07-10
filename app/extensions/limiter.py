from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, TypeVar, cast

from flask import Flask, flash, redirect, request, url_for

F = TypeVar('F', bound=Callable[..., Any])


class RateLimiterExtension(Protocol):
    def init_app(self, app: Flask) -> None: ...

    def limit(self, *args: Any, **kwargs: Any) -> Callable[[F], F]: ...


class _NoopLimiter:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def init_app(self, app: Flask) -> None:
        app.logger.warning('Flask-Limiter is not installed. Login rate limiting is disabled.')

    def limit(self, *args: Any, **kwargs: Any) -> Callable[[F], F]:
        def decorator(func: F) -> F:
            return func

        return decorator


try:
    from flask_limiter import Limiter as _FlaskLimiter
    from flask_limiter.errors import RateLimitExceeded
    from flask_limiter.util import get_remote_address
except ImportError:  # pragma: no cover - keeps local app bootable before dependency install.
    _FlaskLimiter = _NoopLimiter
    RateLimitExceeded = None  # type: ignore[assignment]

    def get_remote_address() -> str:
        return request.remote_addr or '127.0.0.1'


limiter: RateLimiterExtension = cast(
    RateLimiterExtension,
    _FlaskLimiter(key_func=get_remote_address),
)


def register_rate_limit_handlers(app: Flask) -> None:
    if RateLimitExceeded is None:
        return

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(error: Exception):
        if request.endpoint == 'auth.login':
            flash(
                app.config.get(
                    'AUTH_LOGIN_RATE_LIMIT_MESSAGE',
                    'Too many login attempts. Please wait a minute and try again.',
                ),
                'danger',
            )
            return redirect(url_for('auth.login'))

        return str(error), 429
