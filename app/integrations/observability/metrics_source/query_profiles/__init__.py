from __future__ import annotations

from app.integrations.observability.metrics_source.query_profiles.kubernetes_v1 import (
    PROFILE_KEY,
    PROFILE_VERSION,
    QUERIES,
)
from app.integrations.observability.metrics_source.query_profiles.registry import (
    QueryReference,
    query_reference,
    register_query_profile,
    resolve_query_reference,
)
from app.integrations.observability.metrics_source.query_profiles.types import QueryDefinition

register_query_profile(adapter_key='prometheus_http', profile_key=PROFILE_KEY, queries=QUERIES)


class QueryProfileError(LookupError):
    pass


def get_kubernetes_query(key: str) -> QueryDefinition:
    try:
        return QUERIES[key]
    except KeyError as exc:
        raise QueryProfileError(f'Kubernetes metrics query key is not registered: {key}') from exc


def get_kubernetes_query_expression(key: str) -> QueryReference:
    query = get_kubernetes_query(key)
    if query.is_deprecated and query.replacement_key:
        query = get_kubernetes_query(query.replacement_key)
    return query_reference(profile_key=PROFILE_KEY, query=query)


def list_kubernetes_queries(*, domain: str | None = None) -> tuple[QueryDefinition, ...]:
    values = QUERIES.values()
    if domain:
        values = (item for item in values if item.domain == domain)
    return tuple(values)


__all__ = [
    'PROFILE_KEY',
    'PROFILE_VERSION',
    'QueryDefinition',
    'QueryProfileError',
    'QueryReference',
    'get_kubernetes_query',
    'get_kubernetes_query_expression',
    'list_kubernetes_queries',
    'resolve_query_reference',
]
