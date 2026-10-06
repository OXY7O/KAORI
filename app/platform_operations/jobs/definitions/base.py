"""Backward-compatible import surface for registered job definition types."""

from app.platform_operations.jobs.definition_types import JobDefinition, RegisteredJobDispatchResult

__all__ = ['JobDefinition', 'RegisteredJobDispatchResult']
