from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_hero_reads_canonical_posture_and_never_sets_ready_by_default() -> None:
    source = (ROOT / 'app/templates/reports/overview/index.html').read_text()
    service = (ROOT / 'app/reports/overview/service.py').read_text()
    assert 'payload.reporting_posture.label' in source
    assert 'payload.reporting_posture.tone' in source
    assert 'hero_status_label = "Ready"' not in source
    assert "'reporting_posture': get_reporting_posture(" in service


def test_reports_queue_is_source_owned() -> None:
    source = (ROOT / 'app/reports/overview/service.py').read_text()
    assert 'get_queue_readiness(get_reports_queue_name())' in source
    assert "if not bool(worker_context.get('ready')):" in source


def test_missing_worker_evidence_does_not_default_to_ready() -> None:
    source = (ROOT / 'app/reports/overview/presentation.py').read_text()
    assert "normalized.setdefault('report_engine_status', 'Unknown')" in source
    assert "'reason': 'unverified'" in source
