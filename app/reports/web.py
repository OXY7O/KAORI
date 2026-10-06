from __future__ import annotations

import re
from typing import Any

from flask import render_template, url_for
from flask.typing import ResponseReturnValue

_DESCRIPTION_WORD_PATTERN = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")
_SHORT_DESCRIPTION_SUFFIX = 'Maintain governed recovery and retained evidence context.'


def _normalize_reports_unavailable_description(description: str) -> str:
    if len(_DESCRIPTION_WORD_PATTERN.findall(description)) >= 11:
        return description
    return f'{description} {_SHORT_DESCRIPTION_SUFFIX}'


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
        'description': _normalize_reports_unavailable_description(description),
        'reason': reason,
        'retry_url': retry_url,
        'action_label': action_label,
        'overview_url': url_for('reports.overview'),
        'storage_url': url_for('reports.storage'),
        'storage_verify_url': url_for('reports.verify_storage'),
    }
    return render_template('reports/_unavailable.html', payload=payload), status_code
