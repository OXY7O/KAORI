from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VERIFIER = ROOT / 'scripts/verify_integrations_final_lock.py'
QUALITY_GATE = ROOT / 'scripts/quality_gate.sh'
LOCK_DOC = ROOT / 'docs/design/KAORI_INTEGRATIONS_LOCK_V1.md'
REFINEMENT_DOC = ROOT / 'docs/design/KAORI_INTEGRATIONS_LOCK_V1_1.md'
REFINEMENT_AUDIT = ROOT / 'docs/design/audits/KAORI_INTEGRATIONS_FINAL_LOCK_V1_1_AUDIT_2026_08_08.md'
STANDARD = ROOT / 'docs/design/components/INTEGRATIONS_WORKSPACE_STANDARD.md'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_final_lock_verifier_is_wired_into_static_quality_gate() -> None:
    verifier = read(VERIFIER)
    quality_gate = read(QUALITY_GATE)

    assert 'PASS — KAORI Integrations Final Lock v1.1' in verifier
    assert 'verify_integrations_final_lock.py' in quality_gate
    assert 'data-kaori-capability-readiness' in verifier
    assert 'runtime_decision.render(' in verifier
    assert 'data-kaori-provider-configuration-contract' in verifier
    assert 'provider_configuration_contract.render(' in verifier
    assert 'binding_rows|default([])' in verifier
    assert 'workspace_tabs.render(' in verifier


def test_final_lock_document_freezes_current_integration_architecture() -> None:
    lock_doc = read(LOCK_DOC)
    refinement_doc = read(REFINEMENT_DOC)
    refinement_audit = read(REFINEMENT_AUDIT)
    standard = read(STANDARD)

    assert 'Status: Locked baseline' in lock_doc
    assert 'Capability and Validation' in lock_doc
    assert 'Runtime Health and Diagnostics' in lock_doc
    assert 'Configuration is the deliberate exception' in lock_doc
    assert 'registered `binding_rows`' in lock_doc
    assert 'Minimum Full Validation reader explicitly excludes cluster-wide Secret reads' in lock_doc
    assert 'KAORI Integrations Lock v1' in standard
    assert 'Status: Locked refinement baseline' in refinement_doc
    assert 'Configuration Decision rail density' in refinement_doc
    assert 'Prometheus Configuration Decision' in refinement_audit
    assert 'KAORI Integrations Lock v1.1' in standard
    assert 'scripts/verify_integrations_final_lock.py' in standard


def test_retired_integration_presentation_paths_are_removed() -> None:
    obsolete = (
        ROOT / 'app/templates/integrations/partials/_runtime_detail_content.html',
        ROOT / 'app/templates/metrics/partials/_analytics_readiness.html',
    )
    for path in obsolete:
        assert not path.exists()
