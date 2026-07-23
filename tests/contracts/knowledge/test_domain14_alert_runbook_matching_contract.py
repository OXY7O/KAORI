from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_candidate_is_explicitly_non_executable_and_immutable():
    source = (ROOT / 'app/knowledge/matching.py').read_text()
    assert '@dataclass(frozen=True, slots=True)' in source
    assert 'executable: bool = False' in source
    assert 'MappingProxyType(evidence)' in source


def test_ambiguity_and_published_revision_guards_exist():
    source = (ROOT / 'app/knowledge/matching.py').read_text()
    assert 'Ambiguous runbook bindings' in source
    assert "revision.publication_status != 'published'" in source
    assert 'Matched alert evidence is incomplete' in source


def test_binding_is_version_locked_and_delete_restricted():
    model = (ROOT / 'app/models/knowledge.py').read_text()
    migration = (ROOT / 'migrations/versions/20260723_alert_runbook_matching.py').read_text()
    assert 'runbook_revision_id' in model
    assert "ondelete='RESTRICT'" in model
    assert "down_revision = '20260723_runbook_validation'" in migration
