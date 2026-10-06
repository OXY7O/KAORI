from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / '.github/workflows/quality.yml'
DELIVERY = ROOT / 'docs/engineering/KAORI_DELIVERY_WORKFLOW.md'
SPEC = ROOT / 'docs/superpowers/specs/2026-08-30-progressive-ci-evidence-reuse-design.md'
PLAN = ROOT / 'docs/superpowers/plans/2026-08-30-progressive-ci-evidence-reuse.md'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_draft_pr_activity_does_not_acquire_governed_ci_runner() -> None:
    source = read(WORKFLOW)

    assert '      - ready_for_review' in source
    assert '      - converted_to_draft' in source
    assert 'github.event.pull_request.draft == false' in source
    assert 'github.event.pull_request.head.repo.full_name == github.repository' in source


def test_governance_uses_draft_findings_ready_candidate_model() -> None:
    for source in (read(DELIVERY), read(SPEC), read(PLAN)):
        normalized = source.lower()
        assert 'draft pr' in normalized
        assert 'ready for review' in normalized
        assert 'full admission' in normalized


def test_ready_candidate_retains_fail_closed_tree_and_authority_contract() -> None:
    delivery = read(DELIVERY).lower()

    assert 'source tree' in delivery
    assert 'authority fingerprint' in delivery
    assert 'fallback' in delivery
    assert 'local uat' in delivery
