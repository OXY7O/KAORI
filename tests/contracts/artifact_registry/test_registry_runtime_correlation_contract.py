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


def test_runtime_correlation_is_bounded_atomic_and_progress_aware() -> None:
    correlation = (ROOT / 'app/artifact_registry/correlation.py').read_text()
    task = (ROOT / 'app/artifact_registry/correlation_tasks.py').read_text()

    assert 'with Session(db.engine) as materialization_session' in correlation
    assert 'materialization_session.begin()' in correlation
    assert 'materialization_session.query(PodInventory)' in correlation
    assert '.yield_per(normalized_batch_size)' in correlation
    assert 'insert(RegistryWorkloadBinding)' in correlation
    assert 'pending_bindings.clear()' in correlation
    assert 'progress_callback(' in correlation
    assert 'digest_index' in correlation
    assert 'tag_index' in correlation
    assert 'selectinload(RegistryArtifact.tags)' in correlation
    assert 'by_path.get(image.repository' not in correlation
    assert 'filter_current_generation(PodInventory.query, PodInventory)' not in correlation
    assert 'progress_callback=report_correlation_progress' in task
    assert 'self.update_state(' in task
    assert "state='PROGRESS'" in task
    assert "stage='Materializing Runtime Correlation'" in task
