from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, TypeVar, cast

from flask import Flask, flash, make_response, redirect, request, url_for
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
from flask_limiter.util import get_remote_address
from flask_login import current_user

F = TypeVar('F', bound=Callable[..., Any])


class RateLimiterExtension(Protocol):
    def init_app(self, app: Flask) -> None: ...

    def limit(self, *args: Any, **kwargs: Any) -> Callable[[F], F]: ...


limiter: RateLimiterExtension = cast(
    RateLimiterExtension,
    Limiter(key_func=get_remote_address),
)


def register_rate_limit_handlers(app: Flask) -> None:
    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(error: Exception):
        if request.endpoint == 'auth.login':
            from app.auth.audit import record_authentication_activity

            record_authentication_activity(
                action='login',
                username=request.form.get('username', ''),
                source='credentials',
                result='failed',
                reason='rate_limited',
            )
            flash(
                app.config.get(
                    'AUTH_LOGIN_RATE_LIMIT_MESSAGE',
                    'Too many login attempts. Please wait a minute and try again.',
                ),
                'danger',
            )
            return redirect(url_for('auth.login'))

        if request.endpoint in {'auth.sso_start', 'auth.sso_callback'}:
            from app.auth.audit import record_authentication_activity

            provider_key = str((request.view_args or {}).get('provider_key') or 'sso')
            record_authentication_activity(
                action='login',
                username=provider_key,
                source='sso',
                result='failed',
                reason='rate_limited',
            )
            flash(
                app.config.get(
                    'AUTH_SSO_RATE_LIMIT_MESSAGE',
                    'Too many SSO attempts. Please wait a minute and start sign-in again.',
                ),
                'danger',
            )
            return redirect(url_for('auth.login'))

        if (
            request.endpoint
            in {
                'kubernetes_operations.request_secret_reveal',
                'kubernetes_operations.reauthenticate_secret_reveal',
                'kubernetes_operations.reveal_secret_value',
            }
            and current_user.is_authenticated
        ):
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
