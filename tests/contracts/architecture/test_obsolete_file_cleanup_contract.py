from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_obsolete_file_verifier_is_canonical_and_cleanup_helper_is_retired() -> None:
    assert (ROOT / 'scripts/verify_obsolete_files.py').is_file()
    assert not (ROOT / 'scripts/cleanup_obsolete_files.sh').exists()
    audit = (ROOT / 'docs/architecture/REPOSITORY_HYGIENE_AUDIT_20260921.md').read_text(encoding='utf-8')
    assert 'scripts/verify_obsolete_files.py' in audit
    assert 'scripts/cleanup_obsolete_files.sh` is retired' in audit


def test_source_archives_are_ignored_at_repository_root() -> None:
    gitignore = (ROOT / '.gitignore').read_text(encoding='utf-8')
    assert '/*.zip' in gitignore
