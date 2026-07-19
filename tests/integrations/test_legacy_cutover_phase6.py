from pathlib import Path

from app.integrations.legacy_audit import scan_active_source_references


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_active_application_code_has_no_legacy_authority_references() -> None:
    findings = scan_active_source_references(PROJECT_ROOT)
    assert findings == []


def test_legacy_audit_command_is_registered() -> None:
    source = (PROJECT_ROOT / 'app/commands/__init__.py').read_text(encoding='utf-8')
    assert 'from app.commands.integrations import audit_integration_legacy' in source
    assert 'app.cli.add_command(audit_integration_legacy)' in source


def test_audit_is_explicitly_read_only() -> None:
    source = (PROJECT_ROOT / 'app/integrations/legacy_audit.py').read_text(encoding='utf-8')
    forbidden = ('db.session.add(', 'db.session.delete(', 'db.session.commit(', 'db.session.flush(')
    for token in forbidden:
        assert token not in source
