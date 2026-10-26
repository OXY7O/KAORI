from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, cast

from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.extensions.db import db
from app.kubernetes.cluster.onboarding import has_registered_clusters
from app.models.cluster import Cluster, ClusterStatus


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


def get_operations_cluster_posture() -> dict[str, Any]:
    """Summarize persisted cluster connection checks, never a live readiness probe.

    A 'connected' row is only previously committed validation evidence; every
    mutation workflow must still revalidate its selected live Kubernetes target.
    """
    try:
        total, reported = db.session.execute(
            select(
                func.count(Cluster.id),
                func.count(Cluster.id).filter(
                    Cluster.status == ClusterStatus.CONNECTED.value,
                    Cluster.last_check.is_not(None),
                ),
            )
        ).one()
    except SQLAlchemyError:
        db.session.rollback()
        return {
            'connection_label': 'Readiness Unavailable',
            'needs_attention': True,
            'status_title': 'Cluster Readiness Unavailable',
            'status_detail': 'Stored connection evidence cannot be loaded. Validate the integration before operating.',
        }

    total = int(total)
    reported = int(reported)
    remaining = total - reported
    if remaining == 0:
        return {
            'connection_label': f'{reported} Reported Connected',
            'needs_attention': False,
            'status_title': '',
            'status_detail': '',
        }
    return {
        'connection_label': f'{reported} of {total} Reported Connected',
        'needs_attention': True,
        'status_title': 'Cluster Validation Required' if reported == 0 else 'Partial Cluster Validation',
        'status_detail': (
            f'{remaining} registered cluster(s) lack a successful committed connection check. '
            'Review their integration validation; each operation still verifies its live target.'
        ),
    }
