from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_obsolete_file_verifier_and_cleanup_script_are_present() -> None:
    assert (ROOT / 'scripts/verify_obsolete_files.py').is_file()
    assert (ROOT / 'scripts/cleanup_obsolete_files.sh').is_file()


def test_source_archives_are_ignored_at_repository_root() -> None:
    gitignore = (ROOT / '.gitignore').read_text(encoding='utf-8')
    assert '/*.zip' in gitignore
