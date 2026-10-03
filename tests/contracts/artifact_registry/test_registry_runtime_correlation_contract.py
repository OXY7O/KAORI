from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_runtime_correlation_uses_committed_kubernetes_inventory() -> None:
    correlation = (ROOT / 'app/artifact_registry/correlation.py').read_text()
    assert 'PodInventory' in correlation
    assert 'container_images' in correlation
    assert 'KubernetesClient' not in correlation
    assert 'requests.' not in correlation


def test_digest_match_is_stronger_than_tag_match() -> None:
    correlation = (ROOT / 'app/artifact_registry/correlation.py').read_text()
    digest_index = correlation.index("return 'digest', 'strong'")
    tag_index = correlation.index("return 'tag', 'medium'")
    assert digest_index < tag_index
