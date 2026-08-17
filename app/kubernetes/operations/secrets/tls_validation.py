from __future__ import annotations

from typing import Any


def validation_trigger(
    payload: dict[str, Any],
    *,
    form_id: str,
    require_targets: bool = False,
) -> str | None:
    validation = payload.get('validation')
    targets = payload.get('targets') or []
    is_valid = bool(validation is not None and validation.is_valid and validation.parsed_certificate is not None)
    if not is_valid or (require_targets and not targets):
        return None
    return f'{{"kaori:operation-validated":{{"formId":"{form_id}"}}}}'
