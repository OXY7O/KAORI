from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, TypeVar, cast

from flask import Flask, flash, make_response, redirect, request, url_for
from flask_login import current_user

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

        if request.endpoint in {
            'kubernetes_operations.request_secret_reveal',
            'kubernetes_operations.reauthenticate_secret_reveal',
            'kubernetes_operations.reveal_secret_value',
        } and current_user.is_authenticated:
            from app.notifications.service import record_operational_activity

            record_operational_activity(
                user_id=current_user.id,
                event_type='kubernetes_secret_reveal_rate_limited',
                status='warning',
                title='Protected Secret Reveal rate limited',
                message='Too many protected reveal attempts were submitted. Wait before retrying.',
                action_url=url_for('kubernetes_operations.reveal_secret'),
                action_label='Open Protected Secret Reveal',
                action_icon='shield-alert',
                metadata={
                    'endpoint': request.endpoint,
                    'source_ip': request.remote_addr,
                    'secret_value_recorded': False,
                },
                queue_feedback=True,
            )
            reveal_url = url_for('kubernetes_operations.reveal_secret')
            if request.headers.get('HX-Request') == 'true':
                response = make_response('', 429)
                response.headers['HX-Redirect'] = reveal_url
                return response
            return redirect(reveal_url)

        return str(error), 429
