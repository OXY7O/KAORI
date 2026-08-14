from __future__ import annotations

from dataclasses import dataclass

from app.resolver.contracts import ResolverAdapter, ResolverError


@dataclass(frozen=True, slots=True)
class ResolverDescriptor:
    action_key: str
    capability_keys: tuple[str, ...]
    compatibility_profiles: tuple[str, ...]
    rollback_required: bool
    verification_required: bool


class ResolverRegistry:
    """Explicit action-to-adapter registry; unknown actions fail closed."""

    def __init__(self) -> None:
        self._adapters: dict[str, ResolverAdapter] = {}

    def register(self, adapter: ResolverAdapter) -> None:
        action_key = str(getattr(adapter, 'action_key', '')).strip()
        if not action_key:
            raise ResolverError('Resolver adapter requires a non-empty action_key.')
        if action_key in self._adapters:
            raise ResolverError(f'Resolver action is already registered: {action_key}.')
        if not callable(getattr(adapter, 'dry_run', None)) or not callable(getattr(adapter, 'execute', None)):
            raise ResolverError('Resolver adapter must implement dry_run and execute.')
        if not callable(getattr(adapter, 'verify', None)):
            raise ResolverError('Resolver adapter must implement post-action verification.')
        self._adapters[action_key] = adapter

    def resolve(self, action_key: str) -> ResolverAdapter:
        adapter = self._adapters.get(action_key)
        if adapter is None:
            raise ResolverError(f'No resolver adapter is registered for action: {action_key}.')
        return adapter

    def describe(self, action_key: str) -> ResolverDescriptor:
        adapter = self.resolve(action_key)
        return ResolverDescriptor(
            action_key=action_key,
            capability_keys=tuple(sorted(set(getattr(adapter, 'capability_keys', ()) or ()))),
            compatibility_profiles=tuple(sorted(set(getattr(adapter, 'compatibility_profiles', ()) or ()))),
            rollback_required=bool(getattr(adapter, 'rollback_required', False)),
            verification_required=True,
        )

    def registered_actions(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))
