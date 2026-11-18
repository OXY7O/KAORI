from pathlib import Path

from scripts.verify_architecture_boundaries import ImportRecord, scan_imports, validate_boundaries

ROOT = Path(__file__).resolve().parents[3]


def _two_domain_cycle(app_root: Path) -> list[ImportRecord]:
    return [
        ImportRecord(source=app_root / 'alpha' / 'service.py', line=11, target='app.beta.service'),
        ImportRecord(source=app_root / 'beta' / 'service.py', line=23, target='app.alpha.service'),
    ]


def test_unapproved_cycle_reports_source_owned_import_edges(tmp_path: Path) -> None:
    app_root = tmp_path / 'app'
    errors = validate_boundaries(
        app_root,
        _two_domain_cycle(app_root),
        {'cycle_envelopes': [], 'service_form_imports': []},
    )

    assert any('new or expanded top-level dependency cycle: alpha, beta' in error for error in errors)
    assert 'cycle dependency: alpha -> beta via app/alpha/service.py:11' in errors
    assert 'cycle dependency: beta -> alpha via app/beta/service.py:23' in errors


def test_existing_approved_envelope_remains_unchanged(tmp_path: Path) -> None:
    app_root = tmp_path / 'app'
    errors = validate_boundaries(
        app_root,
        _two_domain_cycle(app_root),
        {'cycle_envelopes': [{'domains': ['alpha', 'beta']}], 'service_form_imports': []},
    )

    assert errors == []


def test_infrastructure_automation_does_not_import_integration_provider_modules() -> None:
    app_root = ROOT / 'app'
    records = scan_imports(app_root)
    reverse_edges = [
        (record.source.relative_to(ROOT).as_posix(), record.line, record.target)
        for record in records
        if record.source.is_relative_to(app_root / 'infrastructure_automation')
        and (record.target == 'app.integrations' or record.target.startswith('app.integrations.'))
    ]

    assert not reverse_edges
