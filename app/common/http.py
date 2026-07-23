"""Canonical HTTP request helpers shared by KAORI route modules."""

from __future__ import annotations

from collections.abc import Mapping


def header_is_true(headers: Mapping[str, str], name: str) -> bool:
    """Return whether an HTTP header explicitly carries a true value."""
    return str(headers.get(name, '')).strip().lower() == 'true'


def is_htmx_request(headers: Mapping[str, str] | None = None) -> bool:
    """Return whether the current or supplied request is an HTMX request.

    Supplying ``headers`` keeps the helper usable in pure functional tests and
    non-request adapters. Route code may omit it to use Flask's current request.
    """
    if headers is None:
        from flask import request

        headers = request.headers
    return header_is_true(headers, 'HX-Request')


def htmx_target(headers: Mapping[str, str] | None = None) -> str:
    """Return the normalized HTMX target identifier for the request."""
    if headers is None:
        from flask import request

        headers = request.headers
    return str(headers.get('HX-Target', '')).strip()
