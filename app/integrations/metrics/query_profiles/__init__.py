from __future__ import annotations

from app.integrations.metrics.query_profiles.kubernetes_v1 import PROFILE_KEY, PROFILE_VERSION, QUERIES
from app.integrations.metrics.query_profiles.types import QueryDefinition


class QueryProfileError(LookupError):
    pass


def get_query(key: str) -> QueryDefinition:
    try:
        return QUERIES[key]
    except KeyError as exc:
        raise QueryProfileError(f'Metrics query key is not registered: {key}') from exc


def get_query_expression(key: str) -> str:
    query = get_query(key)
    if query.is_deprecated and query.replacement_key:
        return get_query(query.replacement_key).expression
    return query.expression


def list_queries(*, domain: str | None = None) -> tuple[QueryDefinition, ...]:
    values = QUERIES.values()
    if domain:
        values = (item for item in values if item.domain == domain)
    return tuple(values)


__all__ = [
    'PROFILE_KEY',
    'PROFILE_VERSION',
    'QueryDefinition',
    'QueryProfileError',
    'get_query',
    'get_query_expression',
    'list_queries',
]
