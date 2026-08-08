from __future__ import annotations

from typing import Any

from app.retention.presentation import build_data_lifecycle_context


def build_workspace_context(
    *,
    selected_domain: str,
    active_tab: str,
    include_preview: bool,
    archive_page: int,
    archive_per_page: int,
    archive_status: str,
    archive_trigger: str,
    archive_mode: str,
    archive_storage: str,
    archive_search: str,
    archive_domain: str,
    feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the Platform Operations projection over the shared retention engine."""

    return build_data_lifecycle_context(
        selected_domain=selected_domain,
        active_tab=active_tab,
        include_preview=include_preview,
        archive_page=archive_page,
        archive_per_page=archive_per_page,
        archive_status=archive_status,
        archive_trigger=archive_trigger,
        archive_mode=archive_mode,
        archive_storage=archive_storage,
        archive_search=archive_search,
        archive_domain=archive_domain,
        feedback=feedback,
    )
