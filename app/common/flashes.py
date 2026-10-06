from __future__ import annotations

from flask import flash, session


def flash_once(message: str, category: str = 'message') -> bool:
    """Queue one user-facing flash message only once per redirect chain.

    Flask stores pending messages in ``session['_flashes']``.  Checking that
    queue prevents middleware, authentication handlers, and route handlers from
    adding the same notification repeatedly before the destination page renders.
    """

    normalized_message = str(message).strip()
    normalized_category = str(category or 'message').strip().lower()
    if not normalized_message:
        return False

    pending = session.get('_flashes', ())
    for existing_category, existing_message in pending:
        if (
            str(existing_category).strip().lower() == normalized_category
            and str(existing_message).strip() == normalized_message
        ):
            return False

    flash(normalized_message, normalized_category)
    return True
