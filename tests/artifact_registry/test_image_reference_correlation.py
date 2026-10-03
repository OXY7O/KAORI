from app.artifact_registry.correlation.image_reference import parse_image_reference


def test_parse_digest_reference_with_explicit_registry() -> None:
    parsed = parse_image_reference('registry.example.test/team/api@sha256:abcdef')

    assert parsed.registry_host == 'registry.example.test'
    assert parsed.repository_path == 'team/api'
    assert parsed.tag is None
    assert parsed.digest == 'sha256:abcdef'


def test_parse_mutable_tag_reference_without_fabricating_digest() -> None:
    parsed = parse_image_reference('registry.example.test/team/api:v1.2.3')

    assert parsed.registry_host == 'registry.example.test'
    assert parsed.repository_path == 'team/api'
    assert parsed.tag == 'v1.2.3'
    assert parsed.digest is None


def test_parse_runtime_image_id_digest() -> None:
    parsed = parse_image_reference('containerd://sha256:abcdef')

    assert parsed.registry_host is None
    assert parsed.repository_path is None
    assert parsed.tag is None
    assert parsed.digest == 'sha256:abcdef'


def test_parse_docker_pullable_reference() -> None:
    parsed = parse_image_reference('docker-pullable://harbor.example.test/platform/api@sha256:1234')

    assert parsed.registry_host == 'harbor.example.test'
    assert parsed.repository_path == 'platform/api'
    assert parsed.digest == 'sha256:1234'
