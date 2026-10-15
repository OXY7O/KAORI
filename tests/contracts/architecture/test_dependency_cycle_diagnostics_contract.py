from pathlib import Path

from scripts.verify_architecture_boundaries import ImportRecord, validate_boundaries


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
