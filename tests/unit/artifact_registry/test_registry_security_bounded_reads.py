from __future__ import annotations

from pathlib import Path

from app.artifact_registry.security.presentation import _security_search_pattern

ROOT = Path(__file__).resolve().parents[3]


def test_sql_like_metacharacters_are_escaped_as_literal_search() -> None:
    assert _security_search_pattern('cve_100%') == r'%cve\_100\%%'
    assert _security_search_pattern(r'a\b') == r'%a\\b%'


def test_capability_reads_are_one_grouped_query_after_source_page_selection() -> None:
    source = (ROOT / 'app/artifact_registry/security/presentation.py').read_text(encoding='utf-8')
    matrix = source.split('def _security_source_capabilities(', 1)[1].split('def _security_search_pattern(', 1)[0]
    assert '.group_by(RegistryProject.integration_instance_id)' in matrix
    assert '.all()' in matrix
    assert 'func.sum(case(' in matrix
    assert '.count()' not in matrix
    assert 'for source in scoped_sources:' in matrix

    main = source.split('def build_security(', 1)[1]
    assert main.index('visible_capability_sources, capability_pagination = paginate_sequence(') < main.index(
        'capability_rows = ('
    )
    capability_selection = main.split('capability_sources = (', 1)[1].split(
        'visible_capability_sources, capability_pagination = paginate_sequence(', 1
    )[0]
    assert "if view == 'supply_chain' and supply_section == 'capabilities'" in capability_selection
    assert 'else []' in capability_selection
    assert 'if visible_capability_sources' in main
    assert 'source_capabilities = capability_rows' in main


def test_vulnerability_and_supply_search_escape_wildcards_and_use_stable_order() -> None:
    source = (ROOT / 'app/artifact_registry/security/presentation.py').read_text(encoding='utf-8')
    assert source.count('pattern = _security_search_pattern(search_value)') == 2
    assert source.count('.like(pattern, escape=') >= 9
    assert 'RegistryVulnerability.id.asc()' in source
    assert 'RegistryArtifact.id.asc()' in source


def test_security_fleet_artifact_totals_share_one_scoped_sql_aggregate() -> None:
    source = (ROOT / 'app/artifact_registry/security/presentation.py').read_text()
    evidence = source.split('def _security_scope_evidence(', 1)[1].split('def _security_source_capabilities(', 1)[0]
    assert (
        'artifact_total, evidence_count, signature_observed, sbom_available, coverage_gaps = artifact_scope.with_entities('
        in evidence
    )
    assert 'artifact_scope.with_entities(' in evidence
    assert 'count_if(gap_predicate)' in evidence
    assert 'count_if(evidence_filter)' in evidence
    assert 'artifact_scope.order_by(None).count()' not in evidence
    assert 'artifact_scope.filter(evidence_filter).order_by(None).count()' not in evidence
