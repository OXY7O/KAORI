from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.integrations.metrics.query_profiles.types import QueryDefinition


@dataclass(frozen=True, slots=True)
class QueryTransform:
    operation: str
    args: tuple[str, ...]


class QueryReference(str):
    """Semantic metrics query reference with a current-adapter rendering.

    Analytics code carries the semantic query key/profile. The selected Metrics
    Source adapter renders that reference immediately before execution, allowing
    future query languages to implement the same consumer contract without
    changing Analytics, Reports, or Intelligence call sites.
    """

    key: str
    profile_key: str
    transforms: tuple[QueryTransform, ...]

    def __new__(
        cls,
        expression: str,
        *,
        key: str,
        profile_key: str,
        transforms: tuple[QueryTransform, ...] = (),
    ) -> QueryReference:
        value = str.__new__(cls, expression)
        value.key = key
        value.profile_key = profile_key
        value.transforms = transforms
        return value

    def replace(self, old: str, new: str, count: int = -1) -> QueryReference:
        rendered = str.replace(self, old, new, count)
        return QueryReference(
            rendered,
            key=self.key,
            profile_key=self.profile_key,
            transforms=(*self.transforms, QueryTransform('replace', (old, new, str(count)))),
        )


_PROFILES: dict[tuple[str, str], Mapping[str, QueryDefinition]] = {}


def register_query_profile(
    *,
    adapter_key: str,
    profile_key: str,
    queries: Mapping[str, QueryDefinition],
) -> None:
    identity = (adapter_key.strip().lower(), profile_key.strip().lower())
    if not all(identity):
        raise ValueError('Metrics query profile requires adapter_key and profile_key.')
    existing = _PROFILES.get(identity)
    if existing is not None:
        if dict(existing) != dict(queries):
            raise ValueError(f'Metrics query profile {identity!r} is already registered with different queries.')
        return
    _PROFILES[identity] = queries


def query_reference(*, profile_key: str, query: QueryDefinition) -> QueryReference:
    return QueryReference(query.expression, key=query.key, profile_key=profile_key)


def resolve_query_reference(expression: str, *, adapter_key: str) -> str:
    if not isinstance(expression, QueryReference):
        return str(expression)
    identity = (adapter_key.strip().lower(), expression.profile_key.strip().lower())
    try:
        queries = _PROFILES[identity]
    except KeyError as exc:
        raise LookupError(
            f'No query profile {expression.profile_key!r} is registered for metrics adapter {adapter_key!r}.'
        ) from exc
    try:
        definition = queries[expression.key]
    except KeyError as exc:
        raise LookupError(
            f'Query key {expression.key!r} is not registered in profile {expression.profile_key!r} '
            f'for metrics adapter {adapter_key!r}.'
        ) from exc
    rendered = definition.expression
    for transform in expression.transforms:
        if transform.operation == 'replace':
            old, new, count = transform.args
            rendered = rendered.replace(old, new, int(count))
            continue
        raise LookupError(f'Unsupported metrics query transform: {transform.operation!r}.')
    return rendered
