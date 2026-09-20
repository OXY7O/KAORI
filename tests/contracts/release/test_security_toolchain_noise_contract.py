from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SECURITY_REQUIREMENTS = ROOT / '.github' / 'ci' / 'requirements-security.txt'
URLLIB_SUPPRESSION_OWNERS = (
    ROOT / 'scripts' / 'ci_delivery_context.py',
    ROOT / 'scripts' / 'ci_delivery_notify.py',
)


def test_bandit_b310_suppressions_keep_explanatory_prose_outside_directive() -> None:
    for path in URLLIB_SUPPRESSION_OWNERS:
        source = path.read_text(encoding='utf-8')
        assert '# nosec B310' in source
        assert '# nosec B310 -' not in source


def test_semgrep_security_toolchain_uses_reviewed_current_pin() -> None:
    requirements = SECURITY_REQUIREMENTS.read_text(encoding='utf-8').splitlines()

    assert 'semgrep==1.177.0' in requirements
    assert 'semgrep==1.174.0' not in requirements
