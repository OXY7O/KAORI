from pathlib import Path


def test_job_finalizers_preserve_terminal_state_contract() -> None:
    source = Path('app/jobs/service.py').read_text()
    assert source.count('if job.is_terminal:') >= 3
    assert "if job.is_terminal or job.status == 'cancel_requested':" in source
    assert "if job.status == 'cancel_requested':\n        _terminalize(job, 'canceled')" in source
