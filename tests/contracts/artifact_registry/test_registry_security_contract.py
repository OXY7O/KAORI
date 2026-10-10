from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_security_evidence_is_digest_oriented_and_incremental() -> None:
    models = read('app/models/registry.py')
    collector = read('app/integrations/registry/providers/harbor/security.py')
    sync = read('app/artifact_registry/security/sync.py')

    assert 'class RegistryScanSnapshot' in models
    assert 'class RegistryVulnerability' in models
    assert "UniqueConstraint('repository_id', 'digest'" in models
    assert 'get_vulnerability_report' in collector
    assert '_scan_identity_changed' in collector
    assert 'reuse_existing_scan' in collector
    assert 'RegistryVulnerability(' in sync


def test_security_read_model_is_committed_and_server_paginated() -> None:
    presentation = read('app/artifact_registry/security/presentation.py')

    assert 'RegistryArtifact.query' in presentation
    assert 'RegistryVulnerability.query' in presentation
    assert 'paginate_query(' in presentation
    assert "JobExecution.job_type == 'artifact_registry_security'" in presentation
    assert 'HarborClient' not in presentation


def test_security_workspace_uses_canonical_kaori_components() -> None:
    template = read('app/templates/artifact_registry/partials/_security_workspace.html')

    for shared_component in (
        'components/snapshot_context_bar.html',
        'components/content_tabs.html',
        'components/loading_bar.html',
        'components/section_intro.html',
        'components/operational_callout.html',
        'components/action_button.html',
        'components/operational_metric_card.html',
        'components/operational_section_card.html',
        'components/table.html',
        'components/table_registry.html',
        'components/table_label.html',
        'components/states/_empty_state.html',
    ):
        assert shared_component in template
    assert 'Security Evidence Snapshot' in template
    assert 'Security Evidence Operations' in read(
        'app/templates/artifact_registry/partials/_security_sync_live_state.html'
    )
    assert 'Sync Security Evidence' in template
    assert 'Vulnerability Findings' in template
    assert 'Review committed scanner findings and their current runtime exposure.' in template
    assert 'finding_interpretation' in template
    assert 'finding_empty_state' in template
    assert 'Provider Capability Matrix' in template
    assert 'Artifact Evidence Registry' in template
    assert 'Supply Chain Workspace' in template
    assert 'artifact-registry-security-capability-registry' in template
    assert 'table_ui.inventory_block_header' in template
    assert 'security_registry_header_actions' in template
    assert 'class="{{ table_ui.action_classes() }}"' in template
    assert "{% call section_card.render(\n            'Vulnerability Registry'" not in template
    assert "resource_label='Sources'" in template
    assert '[5, 10, 25, 50]' in template
    assert 'Presence is not trust-policy evaluation.' in template
    assert 'Search CVE, package, repo, or digest…' in template
    assert 'Current critical findings from the latest committed scan evidence.' not in template
    assert 'Current high-severity findings from the latest committed scan evidence.' not in template


def test_security_has_two_level_three_views_above_the_hero() -> None:
    catalog = read('app/common/workspace_navigation_catalog.py')
    navigation = read('app/common/workspace_navigation.py')
    routes = read('app/artifact_registry/routes.py')

    assert "'artifact_registry_security': (" in catalog
    assert "'Vulnerabilities'" in catalog
    assert "'Supply Chain'" in catalog
    assert "return 'artifact_registry_security'" in navigation
    assert "'artifact_registry_security': 'Security'" in navigation
    assert "@artifact_registry_bp.get('/security')" in routes
    assert "@artifact_registry_bp.get('/security/supply-chain')" in routes
    assert "@artifact_registry_bp.post('/security/sync')" in routes
    assert "@artifact_registry_bp.get('/security/sync/status/<string:public_id>')" in routes
    assert "job_key='artifact_registry.security.sync'" in routes
    assert "section=request.args.get('section', '', type=str)" in routes
    assert "section=request.form.get('section', '', type=str)" in routes
    assert "return _security_response('vulnerabilities')" in routes


def test_registry_security_capabilities_are_provider_declared() -> None:
    providers = read('app/integrations/registry/security_collectors.py')
    harbor = read('app/integrations/registry/providers/harbor/security.py')

    assert 'capabilities: frozenset[str]' in providers
    assert "capabilities=frozenset({'vulnerability', 'signature', 'sbom'})" in harbor


def test_registry_scan_evidence_semantics_are_shared_by_dashboard_and_intelligence() -> None:
    contracts = read('app/integrations/registry/security_contracts.py')
    presentation = read('app/artifact_registry/security/presentation.py')
    evaluator = read('app/intelligence/registry_recommendations.py')

    assert "SUCCESSFUL_REGISTRY_SCAN_STATUSES = frozenset({'success', 'finished', 'completed'})" in contracts
    assert 'SUCCESSFUL_REGISTRY_SCAN_STATUSES' in presentation
    assert 'func.lower(RegistryArtifact.scan_status).in_(SUCCESSFUL_REGISTRY_SCAN_STATUSES)' in presentation
    assert 'registry_scan_evidence_ready(artifact.scan_status)' in evaluator
    assert 'if not registry_scan_evidence_ready(artifact.scan_status):' in evaluator


def test_registry_security_finding_states_use_usable_scan_coverage() -> None:
    presentation = read('app/artifact_registry/security/presentation.py')
    template = read('app/templates/artifact_registry/partials/_security_workspace.html')

    assert "coverage_count = scanned_artifacts if view == 'vulnerabilities' else evidence_count" in presentation
    assert "'Security Evidence Not Collected'" in presentation
    assert "'No Provider Scan Evidence'" in presentation
    assert "'Partial Scan Coverage'" in presentation
    assert "'No Vulnerabilities Observed'" in presentation
    assert "'No Findings Match This View'" in presentation
    assert 'KAORI does not trigger provider scans.' in presentation
    assert 'security.finding_empty_state.title' in template


def test_security_scope_labels_are_explicit_and_provider_neutral() -> None:
    scope_logic = read('app/artifact_registry/security/presentation_scope.py')

    assert 'if source_id is not None:' in scope_logic
    assert 'selected_source = scoped_sources[0] if len(scoped_sources) == 1 else None' in scope_logic
    assert "return 'Selected Registry Source', 'No Matching Registry Source'" in scope_logic
    assert 'if provider_label:' in scope_logic
    assert "return provider_label, f'{provider_label} · {len(scoped_sources)} {source_count_label}'" in scope_logic
    assert (
        "return 'All Registry Sources', f'{len(scoped_sources)} Registered Registry {source_count_label}'"
        in scope_logic
    )
    assert scope_logic.index('if source_id is not None:') < scope_logic.index('if provider_label:')


def test_supply_chain_uses_governed_tabs_and_canonical_capability_registry() -> None:
    presentation = read('app/artifact_registry/security/presentation.py')
    template = read('app/templates/artifact_registry/partials/_security_workspace.html')

    assert "supply_section = str(section or 'capabilities').strip().lower()" in presentation
    assert "supply_section not in {'capabilities', 'evidence'}" in presentation
    assert 'paginate_sequence(' in presentation
    assert "'capability_rows': capability_rows" in presentation
    assert "'capability_pagination': capability_pagination" in presentation
    assert "'active_pagination': active_pagination" in presentation
    assert "elif supply_section == 'evidence':" in presentation
    assert 'Review provider signature and SBOM evidence without trust-policy claims.' in presentation
    assert 'content_tabs.render_links(' in template
    assert "section='capabilities'" in template
    assert "section='evidence'" in template
    assert "hx_target='#artifact-registry-supply-chain-workspace'" in template
    assert 'name="section" value="capabilities"' in template
    assert 'name="section" value="evidence"' in template
    assert "'Search source or provider…'" in template
    assert 'registry.footer(' in template


def test_supply_chain_tables_use_standard_view_more_native_dialogs() -> None:
    workspace = read('app/templates/artifact_registry/partials/_security_workspace.html')
    modals = read('app/templates/artifact_registry/partials/_security_supply_chain_detail_modals.html')

    assert 'artifact_registry/partials/_security_supply_chain_detail_modals.html' in workspace
    assert workspace.count('View More') >= 2
    assert workspace.count('data-kaori-dialog-open') >= 2
    assert 'Provider Capability Matrix' in workspace
    assert 'Artifact Evidence Registry' in workspace
    assert 'table_ui.header_cell_classes(action=true)' in workspace
    assert 'colspan="7"' in workspace

    assert 'data-kaori-native-dialog' in modals
    assert 'data-kaori-dialog-close' in modals
    assert 'data-artifact-registry-provider-capability-detail' in modals
    assert 'data-artifact-registry-provider-capability-detail-v2' in modals
    assert 'data-artifact-registry-artifact-evidence-detail' in modals
    assert 'data-artifact-registry-artifact-evidence-detail-v2' in modals
    assert 'data-artifact-registry-capability-coverage' in modals
    assert 'data-artifact-registry-artifact-snapshot' in modals
    assert 'data-artifact-registry-supply-chain-evidence' in modals
    assert 'data-artifact-registry-security-snapshot-summary' in modals
    assert 'Committed Security Capability Scope' in modals
    assert 'Capability Coverage' in modals
    assert 'Artifact Snapshot' in modals
    assert 'Supply Chain Evidence' in modals
    assert 'Security Snapshot' in modals
    assert 'Provider Evidence Boundary' in modals
    assert 'Evidence Interpretation' in modals
    assert '{{ row.digest }}' in modals
    assert 'break-all' in modals
    assert 'text-left' in modals
    assert 'Presence is not trust-policy evaluation.' not in modals
    assert 'Observed presence is not a KAORI trust-policy decision.' in modals
    assert 'No live provider request.' in modals
    assert 'Evidence Scope' not in modals


def test_harbor_security_refresh_is_repository_resilient_without_overriding_provider_timeout() -> None:
    collector = read('app/integrations/registry/providers/harbor/security.py')
    tasks = read('app/artifact_registry/security/tasks.py')

    assert '_SECURITY_DISCOVERY_PAGE_SIZES = (20, 10)' in collector
    assert 'build_client(instance, transport_retries=_SECURITY_TRANSPORT_RETRIES)' in collector
    assert 'repository_security_refresh_unavailable' in collector
    assert "'repository_failure_count': len(state.repository_failures)" in collector
    assert "'repository_failures': state.repository_failures[:_MAX_REPOSITORY_FAILURE_EVIDENCE]" in collector
    assert 'except HarborAuthError:' in collector
    assert 'Harbor security discovery was unavailable for every committed repository' in collector
    assert 'partial_source_count' in tasks
    assert 'repository_failure_count' in tasks
    assert "'warning_evidence': summary.warning_evidence[:50]" in tasks
    assert 'partial=bool(failures or has_partial_refresh)' in tasks


def test_vulnerability_runtime_drilldown_preserves_artifact_context() -> None:
    presentation = read('app/artifact_registry/security/presentation.py')
    template = read('app/templates/artifact_registry/partials/_security_workspace.html')
    modals = read('app/templates/artifact_registry/partials/_security_supply_chain_detail_modals.html')

    assert "'artifact_id': int(artifact.id)" in presentation
    assert "url_for('artifact_registry.runtime', artifact_id=row.artifact_id)" in modals
    assert 'Open Runtime Usage' in modals
    assert 'source_id=security.filters.source_id' in template
    assert "supply_chain_detail.vulnerability(row, vulnerability_dialog_id)" in template



def test_vulnerability_registry_compact_rows_preserve_complete_committed_evidence() -> None:
    from jinja2 import Environment

    workspace = read('app/templates/artifact_registry/partials/_security_workspace.html')
    detail = read('app/templates/artifact_registry/partials/_security_supply_chain_detail_modals.html')
    presentation = read('app/artifact_registry/security/presentation.py')

    Environment().parse(workspace)
    Environment().parse(detail)

    # The vulnerability table alone uses a bounded six-column design.
    vulns = workspace.split("table_ui.table_classes('min-w-[68rem] !table-fixed')", 1)[1].split(
        "{% else %}\n                                        <table", 1
    )[0]
    assert 'w-[19%]">Finding</th>' in vulns
    assert 'w-[21%]">Artifact</th>' in vulns
    assert 'w-[23%]">Package / Fix</th>' in vulns
    assert 'w-[14%]">Runtime Exposure</th>' in vulns
    assert 'w-[13%]">Evidence</th>' in vulns
    assert 'w-[10%]">Details</th>' in vulns
    assert vulns.count('row.severity_label, severity_tone') == 1
    assert 'row.installed_version' in vulns
    assert 'row.fix_available' in vulns
    assert "row.runtime_exposure_count" in vulns
    assert "status_indicator_label('Not Observed', 'unknown')" in vulns
    assert "row.freshness.label, row.freshness.tone" in vulns
    # Restore existing icon-bearing title_cell (not a new styling component).
    # Every registry identity renders one semantic icon without duplicating
    # the severity or freshness evidence labels.
    assert "table_ui.title_cell(row.vulnerability_id, '', 'shield-alert')" in vulns
    assert "table_ui.title_cell(row.repository, 'Project: ' ~ row.project, 'package-search')" in vulns
    assert "table_ui.title_cell(row.source_name, '', 'blocks')" in vulns
    assert vulns.count("table_ui.title_cell(row.vulnerability_id, '', 'shield-alert')") == 1
    assert vulns.count("table_ui.title_cell(row.repository, 'Project: ' ~ row.project, 'package-search')") == 1
    assert vulns.count("table_ui.title_cell(row.source_name, '', 'blocks')") == 1
    assert 'title="{{ row.package }}"' in vulns
    assert "macro title_cell(name, supporting_text='', icon='')" in read(
        'app/templates/components/table_primitives.html'
    )
    assert "vulnerability_dialog_id = 'artifact-registry-vulnerability-detail-' ~ row.id" in vulns
    assert 'data-kaori-dialog-open' in vulns
    assert 'data-dialog-target="{{ vulnerability_dialog_id }}"' in vulns
    assert 'supply_chain_detail.vulnerability(row, vulnerability_dialog_id)' in vulns
    assert 'colspan="6"' in vulns
    assert 'security.finding_empty_state.title' in vulns

    # The shell is the existing approved, keyboard-closeable KAORI dialog.
    assert '{% macro vulnerability(row, dialog_id)' in detail
    assert "dialog_id," in detail
    assert "data-artifact-registry-vulnerability-detail" in detail
    assert 'data-kaori-native-dialog' in detail
    assert 'data-kaori-dialog-close' in detail

    # Full artifact and package identities never depend on the truncated table.
    for field in (
        'row.vulnerability_id', 'row.severity_label', 'row.package',
        'row.installed_version', 'row.fixed_version', 'row.project',
        'row.repository', 'row.digest', 'row.source_name', 'row.provider_label',
        'row.observed_at|user_datetime', 'row.runtime_exposure_count',
        'row.freshness.label',
    ):
        assert field in detail
    assert 'No committed Kubernetes workload binding is currently observed' in detail
    assert 'does not establish that the finding is remediated' in detail
    assert "row.runtime_exposure_count" in detail
    assert "url_for('artifact_registry.runtime', artifact_id=row.artifact_id)" in detail

    # One modal per paginated finding; no provider calls or new scan logic.
    assert "'id': int(item.id)" in presentation
    assert "RegistryWorkloadBinding.query" in presentation
    assert 'HarborClient' not in presentation
    assert "registry.footer(" in workspace
    assert '[5, 10, 25, 50]' in workspace


def test_security_sync_revalidates_stale_targets_and_heartbeats_repository_discovery() -> None:
    providers = read('app/artifact_registry/security/providers.py')
    sync = read('app/artifact_registry/security/sync.py')
    harbor = read('app/integrations/registry/providers/harbor/security.py')
    client = read('app/integrations/registry/providers/harbor/client.py')

    assert 'SecurityTargetCurrentPredicate' in providers
    assert '_build_registry_security_target_current_predicate' in sync
    assert 'target_is_current,' in sync
    assert 'skipped stale' in harbor
    assert "'stale_target_skip_count': state.stale_target_skip_count" in harbor
    assert 'discovering security page {page}' in harbor
    assert 'registry_scan_evidence_ready(scan_status)' in harbor
    assert 'page_callback: Callable[[int], None] | None = None' in client
