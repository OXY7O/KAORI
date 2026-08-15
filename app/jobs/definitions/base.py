"""Backward-compatible import surface for registered job definition types."""

from app.jobs.definition_types import JobDefinition, RegisteredJobDispatchResult

__all__ = ['JobDefinition', 'RegisteredJobDispatchResult']
