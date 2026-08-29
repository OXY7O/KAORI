from __future__ import annotations

import secrets

from flask import Flask, Response, g

_INLINE_SCRIPT_OPEN = '<script>'
_PERMISSIONS_POLICY = 'camera=(), microphone=(), geolocation=()'


def _content_security_policy(nonce: str) -> str:
    # Alpine's standard runtime evaluates x-* expressions dynamically. Keep the
    # compatibility allowance explicit and bounded to script evaluation while
    # inline script execution itself remains nonce-protected.
    return '; '.join(
        (
            "default-src 'self'",
            "base-uri 'self'",
            "object-src 'none'",
            "frame-ancestors 'none'",
            "form-action 'self'",
            f"script-src 'self' 'nonce-{nonce}' 'unsafe-eval'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: blob:",
            "font-src 'self' data:",
            "connect-src 'self'",
        )
    )


def _protect_inline_scripts(response: Response, nonce: str) -> None:
    if response.direct_passthrough:
        return

    document = response.get_data(as_text=True)
    if _INLINE_SCRIPT_OPEN not in document:
        return

    # KAORI's trusted inline bootstrap blocks use the bare <script> opening
    # tag. External scripts retain src= and are already admitted by 'self'.
    response.set_data(document.replace(_INLINE_SCRIPT_OPEN, f'<script nonce="{nonce}">'))


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

        if response.mimetype == 'text/html':
            nonce = g.csp_nonce
            _protect_inline_scripts(response, nonce)
            response.headers['Content-Security-Policy'] = _content_security_policy(nonce)

        return response
