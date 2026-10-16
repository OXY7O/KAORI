from __future__ import annotations

from types import SimpleNamespace

from app.intelligence.registry_recommendations import _tag_only_finding_key


def _parts(
    *, binding_id: int = 1, pod: str = 'api-1', image: str = 'harbor.example/demo/api:uat', digest: str = 'sha256:abc'
):
    artifact = SimpleNamespace(digest=digest)
    identity = SimpleNamespace(id=6)
    binding = SimpleNamespace(
        id=binding_id,
        cluster_id='kubernetes-x300',
        namespace='tenant-adopt-quota-uat',
        pod_name=pod,
        image_reference=image,
    )
    return artifact, identity, binding


def test_tag_only_finding_key_survives_binding_rebuild() -> None:
    artifact, identity, original = _parts(binding_id=1)
    _, _, regenerated = _parts(binding_id=9001)
    rule = 'registry.runtime.tag_only_correlation'
    assert _tag_only_finding_key(rule, artifact, identity, original) == _tag_only_finding_key(
        rule, artifact, identity, regenerated
    )
    assert _tag_only_finding_key(rule, artifact, identity, original).startswith(rule + ':')


def test_tag_only_finding_key_distinguishes_real_resource_identity_changes() -> None:
    artifact, identity, original = _parts()
    reference = _tag_only_finding_key('registry.runtime.tag_only_correlation', artifact, identity, original)

    changed = [
        _parts(pod='api-2'),
        _parts(image='harbor.example/demo/api:other'),
        _parts(digest='sha256:changed'),
    ]
    for new_artifact, new_identity, new_binding in changed:
        assert (
            _tag_only_finding_key('registry.runtime.tag_only_correlation', new_artifact, new_identity, new_binding)
            != reference
        )
    changed_source = SimpleNamespace(id=7)
    assert (
        _tag_only_finding_key('registry.runtime.tag_only_correlation', artifact, changed_source, original) != reference
    )
