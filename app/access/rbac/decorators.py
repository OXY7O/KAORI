from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import TypeVar, cast

from flask import abort
from flask_login import current_user, login_required

F = TypeVar('F', bound=Callable[..., object])


def permission_required(permission_key: str) -> Callable[[F], F]:
    def decorator(view_func: F) -> F:
        @wraps(view_func)
        @login_required
        def wrapped(*args: object, **kwargs: object) -> object:
            has_permission = getattr(current_user, 'has_permission', None)
            if not callable(has_permission) or not has_permission(permission_key):
                abort(403)
            return view_func(*args, **kwargs)

        return cast(F, wrapped)

    return decorator


def any_permission_required(*permission_keys: str) -> Callable[[F], F]:
    def decorator(view_func: F) -> F:
        @wraps(view_func)
        @login_required
        def wrapped(*args: object, **kwargs: object) -> object:
            has_permission = getattr(current_user, 'has_permission', None)
            if not callable(has_permission) or not any(
                has_permission(permission_key) for permission_key in permission_keys
            ):
                abort(403)
            return view_func(*args, **kwargs)

        return cast(F, wrapped)

    return decorator
