from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from app.artifact_registry.correlation import (
    _container_rows,
    _match,
    _normalized_registry_host,
    parse_image_reference,
)
from app.models.inventory import PodInventory
from app.models.registry import RegistryArtifact


def _artifact() -> RegistryArtifact:
    return cast(
        RegistryArtifact,
        SimpleNamespace(
            digest='sha256:abc',
            repository=SimpleNamespace(
                name='service',
                project=SimpleNamespace(name='team'),
            ),
            tags=[SimpleNamespace(name='latest')],
        ),
    )


@pytest.mark.parametrize(
    ('image', 'host'),
    [
        ('harbor-other.example/team/service@sha256:abc', 'harbor.example'),
        ('team/service@sha256:abc', 'harbor.example'),
        ('harbor.example/team/service@sha256:abc', None),
        ('harbor.example/team/service:latest', None),
    ],
)
def test_runtime_correlation_does_not_infer_missing_or_foreign_registry_authority(image, host):
    assert _match(parse_image_reference(image), _artifact(), registry_host=host) is None


def test_runtime_correlation_keeps_digest_and_mutable_tag_confidence():
    artifact = _artifact()
    digest = parse_image_reference('harbor.example/team/service@sha256:abc')
    tag = parse_image_reference('harbor.example/team/service:latest')
    assert _match(digest, artifact, registry_host='harbor.example') == ('digest', 'strong')
    assert _match(tag, artifact, registry_host='harbor.example') == ('tag', 'medium')
    assert (
        _match(
            parse_image_reference('harbor.example/team/service@sha256:wrong'),
            artifact,
            registry_host='harbor.example',
        )
        is None
    )


def test_registry_authority_retains_configured_nondefault_port():
    assert _normalized_registry_host('Harbor.Example:5000') == 'harbor.example:5000'
    assert _normalized_registry_host('harbor.example:443') == 'harbor.example'
    assert _normalized_registry_host('harbor.example:not-a-port') is None


def test_distinct_containers_and_init_containers_keep_identity():
    pod = cast(
        PodInventory,
        SimpleNamespace(
            container_names=['api', 'sidecar'],
            container_images=['harbor.example/team/service:latest'] * 2,
            init_container_images=['harbor.example/team/service:latest'],
        ),
    )
    assert list(_container_rows(pod)) == [
        ('harbor.example/team/service:latest', 'api', 'container', 0),
        ('harbor.example/team/service:latest', 'sidecar', 'container', 1),
        ('harbor.example/team/service:latest', 'Init container 1', 'init_container', 0),
    ]
