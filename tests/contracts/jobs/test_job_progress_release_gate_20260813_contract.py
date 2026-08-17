from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_job_progress_final_lock_verifier_is_release_gated() -> None:
    quality_gate = read('scripts/quality_gate.sh')
    registry = read('scripts/release_surface_registry.py')

    assert (ROOT / 'scripts/verify_job_progress_final_lock.py').exists()
    assert 'python scripts/verify_job_progress_final_lock.py' in quality_gate
    assert "'scripts/verify_job_progress_final_lock.py'" in registry


def test_job_progress_runtime_geometry_and_loading_labels_are_canonical() -> None:
    progress = read('app/templates/components/progress_bar.html')
    active = read('app/templates/jobs/executions/partials/_active_jobs.html')
    queue = read('app/templates/jobs/executions/partials/_queue_activity.html')

    assert '{% macro notification_track_classes()' in progress
    assert 'h-1.5 w-full overflow-hidden rounded-full' in progress
    assert 'notification_indeterminate(' in progress
    assert 'w-1/4 rounded-full bg-kaori-primary/55' in progress
    assert "label='Refreshing Active Work'" in active
    assert "label='Refreshing Queue Activity and Worker Readiness'" in queue
