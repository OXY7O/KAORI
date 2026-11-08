from __future__ import annotations

from flask import abort, request


def _overview_provider_id() -> int | None:
    """Treat malformed explicit scope IDs as unavailable, not All Providers."""
    raw = request.args.get('provider_id')
    if raw is None or not raw.strip():
        return None
    try:
        provider_id = int(raw)
    except (TypeError, ValueError):
        abort(404)
    if provider_id < 1:
        abort(404)
    return provider_id


def _inventory_source_id() -> int | None:
    """An invalid explicit Registry source filter must not expand to all providers."""
    raw = request.args.get('source_id')
    if raw is None or not raw.strip():
        return None
    try:
        source_id = int(raw)
    except (TypeError, ValueError):
        abort(404)
    if source_id < 1:
        abort(404)
    return source_id
