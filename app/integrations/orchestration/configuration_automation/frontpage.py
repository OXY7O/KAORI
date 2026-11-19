"""Ansible provider landing: canonical registered connections, not worker stats."""

from __future__ import annotations

from typing import Any

from app.integrations.orchestration.configuration_automation.providers.ansible.service import list_connections
from app.kubernetes.cluster.constants import ENVIRONMENTS


def build_ansible_frontpage(
    *, query: str = '', environment: str = '', page: int = 1, per_page: int = 5
) -> dict[str, Any]:
    selected_environment = environment if environment in {name for name, _ in ENVIRONMENTS} else ''
    rows, pagination, stats = list_connections(
        query=query, environment=selected_environment, page=page, per_page=per_page
    )
    return {
        'rows': rows,
        'pagination': pagination,
        'stats': stats,
        'selected_query': query[:80],
        'selected_environment': selected_environment,
        'environment_options': ENVIRONMENTS,
    }
