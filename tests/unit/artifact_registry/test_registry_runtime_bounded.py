from __future__ import annotations

from datetime import UTC, datetime

from app.artifact_registry.correlation import (
    IndexedArtifact,
    _match_indexed,
    parse_image_reference,
)


def _candidate(tag: str | None = None) -> IndexedArtifact:
    return IndexedArtifact(
        id=7,
        repository='team/service',
        digest='sha256:abc',
        tag=tag,
        host='harbor.example:5000',
        observed_at=datetime(2026, 10, 12, tzinfo=UTC),
    )


def test_scalar_artifact_index_preserves_digest_and_tag_match():
    digest = parse_image_reference('harbor.example:5000/team/service@sha256:abc')
    tag = parse_image_reference('harbor.example:5000/team/service:stable')
    assert _match_indexed(digest, _candidate()) == ('digest', 'strong')
    assert _match_indexed(tag, _candidate('stable')) == ('tag', 'medium')
    assert _match_indexed(tag, _candidate('old')) is None


def test_scalar_artifact_index_rejects_foreign_or_unresolved_registry():
    image = parse_image_reference('foreign.example:5000/team/service@sha256:abc')
    assert _match_indexed(image, _candidate()) is None
    assert (
        _match_indexed(
            parse_image_reference('harbor.example:5000/team/service@sha256:abc'),
            IndexedArtifact(
                id=7,
                repository='team/service',
                digest='sha256:abc',
                tag=None,
                host=None,
                observed_at=datetime(2026, 10, 12, tzinfo=UTC),
            ),
        )
        is None
    )
