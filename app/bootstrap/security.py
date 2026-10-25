from __future__ import annotations

import secrets

from flask import Flask, Response, g

_TRUSTED_INLINE_SCRIPT_OPENINGS = (
    '<script>',
    '<script data-kaori-prepaint-bootstrap="app-shell">',
    '<script data-kaori-prepaint-bootstrap="auth-theme">',
)
_PERMISSIONS_POLICY = 'camera=(), microphone=(), geolocation=()'


def _content_security_policy(nonce: str, *, allow_turnstile: bool = False) -> str:
    # Alpine's standard runtime evaluates x-* expressions dynamically. Keep the
    # compatibility allowance explicit and bounded to script evaluation while
    # inline script execution itself remains nonce-protected.
    script_sources = f"script-src 'self' 'nonce-{nonce}' 'unsafe-eval'"
    connection_sources = "connect-src 'self'"
    frame_sources: tuple[str, ...] = ()
    if allow_turnstile:
        # Fixed, source-owned Cloudflare endpoints only. Never use wildcard
        # script/frame origins or site-key-derived hosts in security headers.
        script_sources += ' https://challenges.cloudflare.com'
        connection_sources += ' https://challenges.cloudflare.com'
        frame_sources = ('frame-src https://challenges.cloudflare.com',)
    return '; '.join(
        (
            "default-src 'self'",
            "base-uri 'self'",
            "object-src 'none'",
            "frame-ancestors 'none'",
            "form-action 'self'",
            script_sources,
            "script-src-attr 'none'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: blob:",
            "font-src 'self' data:",
            connection_sources,
            *frame_sources,
        )
    )


def _protect_inline_scripts(response: Response, nonce: str) -> None:
    if response.direct_passthrough:
        return

    document = response.get_data(as_text=True)
    if '<script' not in document:
        return

    # Keep nonce admission fail-closed. Only the historically trusted bare
    # bootstrap opening and the two explicitly governed pre-paint markers are
    # rewritten. Arbitrary inline script attributes must not become trusted
    # merely because they appear in an HTML response.
    for opening in _TRUSTED_INLINE_SCRIPT_OPENINGS:
        protected_opening = f'{opening[:-1]} nonce="{nonce}">'
        document = document.replace(opening, protected_opening)

    response.set_data(document)


def register_security_headers(app: Flask) -> None:
    """Register KAORI's centralized HTTP response-security baseline."""

    @app.before_request
    def create_csp_nonce() -> None:
        g.csp_nonce = secrets.token_urlsafe(24)

    @app.after_request
    def apply_security_headers(response: Response) -> Response:
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Permissions-Policy'] = _PERMISSIONS_POLICY
        response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'

        if response.mimetype == 'text/html':
            nonce = g.csp_nonce
            allow_turnstile = (
                'data-kaori-turnstile-active="true"' in response.get_data(as_text=True)
                and response.status_code == 200
            )
            _protect_inline_scripts(response, nonce)
            response.headers['Content-Security-Policy'] = _content_security_policy(
                nonce, allow_turnstile=allow_turnstile
            )
            response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
            # Turnstile embeds an external challenge iframe. Only its
            # login form relaxes the cross-origin isolation needed for it.
            response.headers['Cross-Origin-Embedder-Policy'] = 'unsafe-none' if allow_turnstile else 'require-corp'

        return response
