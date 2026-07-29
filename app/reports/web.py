from __future__ import annotations

from typing import Any

from flask import render_template, url_for
from flask.typing import ResponseReturnValue


def render_reports_unavailable(
    *,
    page_title: str,
    description: str,
    reason: str,
    retry_url: str,
    action_label: str = 'Retry',
    status_code: int = 503,
) -> ResponseReturnValue:
    payload: dict[str, Any] = {
        'page_title': page_title,
        'description': description,
        'reason': reason,
        'retry_url': retry_url,
        'action_label': action_label,
        'overview_url': url_for('reports.overview'),
        'storage_url': url_for('reports.storage'),
    }
    return render_template('reports/_unavailable.html', payload=payload), status_code
