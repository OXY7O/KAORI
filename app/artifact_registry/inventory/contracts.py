from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class RegistryTagEvidence:
    name: str
    provider_native_id: str | None = None
    push_time: datetime | None = None
    pull_time: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RegistryArtifactEvidence:
    digest: str
    provider_native_id: str | None = None
    artifact_type: str | None = None
    media_type: str | None = None
    manifest_media_type: str | None = None
    size_bytes: int | None = None
    push_time: datetime | None = None
    pull_time: datetime | None = None
    tags: tuple[RegistryTagEvidence, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RegistryRepositoryEvidence:
    name: str
    provider_native_id: str | None = None
    description: str | None = None
    artifact_count: int | None = None
    pull_count: int | None = None
    provider_created_at: datetime | None = None
    provider_updated_at: datetime | None = None
    artifacts: tuple[RegistryArtifactEvidence, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RegistryProjectEvidence:
    name: str
    provider_native_id: str | None = None
    is_public: bool | None = None
    repository_count: int | None = None
    provider_created_at: datetime | None = None
    provider_updated_at: datetime | None = None
    repositories: tuple[RegistryRepositoryEvidence, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RegistryInventoryEvidence:
    provider_key: str
    integration_instance_id: int
    observed_at: datetime
    projects: tuple[RegistryProjectEvidence, ...]

    @property
    def repository_count(self) -> int:
        return sum(len(project.repositories) for project in self.projects)

    @property
    def artifact_count(self) -> int:
        return sum(len(repository.artifacts) for project in self.projects for repository in project.repositories)

    @property
    def tag_count(self) -> int:
        return sum(
            len(artifact.tags)
            for project in self.projects
            for repository in project.repositories
            for artifact in repository.artifacts
        )
