from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, cast

from flask import flash, redirect, render_template, request, url_for

from app.kubernetes.cluster.onboarding import has_registered_clusters


def _blocked_page_description(operation_label: str, page_description: str | None) -> str:
    if page_description:
        return page_description.strip()
    return f'Review {operation_label} readiness for the selected cluster.'


def cluster_required[ViewT: Callable[..., Any]](
    operation_label: str,
    *,
    page_title: str | None = None,
    page_description: str | None = None,
) -> Callable[[ViewT], ViewT]:
    """Run the Kubernetes cluster prerequisite only after route authorization."""

    def decorator(view: ViewT) -> ViewT:
        @wraps(view)
        def wrapped(*args: Any, **kwargs: Any):
            if has_registered_clusters() is not False:
                return view(*args, **kwargs)

            is_partial = request.headers.get('HX-Request') == 'true' or request.args.get('partial_mode')
            if is_partial:
                return render_template('components/cluster/_onboarding_banner.html'), 409

            if request.method == 'GET':
                return (
                    render_template(
                        'kubernetes/operations/cluster_required.html',
                        requested_operation=operation_label,
                        requested_page_title=page_title or operation_label,
                        requested_page_description=_blocked_page_description(operation_label, page_description),
                    ),
                    409,
                )

            flash('Add a Kubernetes cluster before running Kubernetes operations.', 'warning')
            return redirect(url_for('integrations.kubernetes'))

        return cast(ViewT, wrapped)

    return decorator


def validate_then_apply[ResultT](
    *,
    validate: Callable[[], object],
    apply: Callable[[], ResultT],
    prepare_apply: Callable[[], object] | None = None,
) -> ResultT:
    """Run validation before a Kubernetes mutation and abort apply on failure."""
    validate()
    if prepare_apply is not None:
        prepare_apply()
    return apply()
