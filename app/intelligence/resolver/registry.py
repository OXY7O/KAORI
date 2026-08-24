"""Compatibility surface for the shared resolver registry.

The shared registry requires post-action verification-capable adapters before registration.
"""

from app.common.resolver_registry import ResolverDescriptor, ResolverRegistry

__all__ = ['ResolverDescriptor', 'ResolverRegistry']
