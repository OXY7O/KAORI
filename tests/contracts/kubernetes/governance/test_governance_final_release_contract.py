from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_governance_routes_do_not_short_circuit_authorization_with_blueprint_before_request() -> None:
    source = read('app/kubernetes/governance/routes.py')
    assert '@governance_bp.before_request' not in source
    assert 'block_clusterless_governance_actions' not in source


def test_tls_routes_own_authorized_clusterless_handling() -> None:
    source = read('app/kubernetes/governance/tls_certificates/routes.py')
    assert 'def _clusterless_read_response()' in source
    assert 'def _clusterless_detail_response()' in source
    assert 'def _clusterless_sync_response()' in source
    assert source.index("@permission_required('tls_certificates.view')\ndef tls_certificates_index") < source.index(
        'clusterless_response = _clusterless_read_response()'
    )


def test_governance_overview_reuses_authorized_tls_snapshot_and_operations_compact_catalog() -> None:
    routes = read('app/kubernetes/governance/routes.py')
    overview = read('app/templates/kubernetes/governance/overview/index.html')
    service = read('app/kubernetes/governance/tls_certificates/service.py')
    snapshot_partial = read('app/templates/kubernetes/governance/tls_certificates/partials/_snapshot_context.html')
    shared_card = read('app/templates/components/workspace_link_card.html')
    standard = read('docs/design/patterns/KUBERNETES_TLS_CERTIFICATE_GOVERNANCE.md')

    assert "@permission_required('governance.view')\ndef overview" in routes
    assert "can_view_tls = current_user.has_permission('tls_certificates.view')" in routes
    assert 'if can_view_tls and has_registered_clusters() is True:' in routes
    assert 'tls_snapshot = get_tls_collection_snapshot()' in routes
    assert 'get_tls_certificate_page' not in routes
    permission_position = routes.index('can_view_tls = current_user.has_permission(')
    readiness_position = routes.index('if can_view_tls and has_registered_clusters() is True:')
    snapshot_position = routes.index('tls_snapshot = get_tls_collection_snapshot()')
    assert permission_position < readiness_position < snapshot_position

    assert 'def get_tls_collection_snapshot() -> dict[str, Any]:' in service
    assert 'check_tls_governance_schema_readiness()' in service
    assert 'return _collection_snapshot(' in service
    assert "selected_cluster_id=''," in service
    assert "summary={'total': total}" in service
    assert 'TLSCertificateInventory.id' in service
    assert 'get_tls_certificate_page({})' not in routes
    assert 'TLS Collection Snapshot' in snapshot_partial
    assert 'snapshot_context.render(' in snapshot_partial

    for token in (
        'Kubernetes Governance',
        'Review Kubernetes governance controls, evidence, and ownership.',
        'Governance Scope',
        'Governance Capabilities',
        'Open independent governance workspaces with explicit evidence and source-readiness status.',
        'sm:grid-cols-2',
        "'title': 'TLS Certificates'",
        "'action': 'Open TLS Certificates' if can_view_tls else 'View Permission Required'",
        'workspace_card.render(',
        'compact=true',
        'Governance Model',
        'Governance Operating Model',
        'Provider Authority',
        'Policy & Guardrails',
        'Committed Evidence',
        'Controlled Handoffs',
        'KAORI applies governance policy and authorization guardrails without cloning the provider control plane.',
        'Open Cluster Integrations',
        'View Permission Required',
        'header_badge=capability_badge',
        "info_tip.render('governance-operating-model-guide'",
        "variant='guide'",
        'header_badge=model_guide',
        'overflow-hidden rounded-xl border border-outline-subtle',
    ):
        assert token in overview

    assert '{% if can_view_tls and tls_snapshot is not none %}' in overview
    assert "{% with payload={'snapshot': tls_snapshot} %}" in overview
    assert 'kubernetes/governance/tls_certificates/partials/_snapshot_context.html' in overview
    assert overview.index('partials/_snapshot_context.html') < overview.index("section_intro.render('Governance Scope'")
    assert overview.index("section_intro.render('Governance Scope'") < overview.index(
        "section_intro.render('Governance Model'"
    )
    assert '{% if cluster_onboarding.is_blocked %}' in overview
    assert 'components/cluster/_onboarding_banner.html' in overview
    assert 'components/snapshot_context_bar.html' not in overview
    assert 'Governance Control Context' not in overview
    assert 'New governance capabilities join this catalog only after implementation' not in overview
    assert '[grid-template-columns:repeat(auto-fit' not in overview
    assert "action_href=url_for('governance.tls_certificates')" not in overview
    assert 'get_tls_certificate_page' not in overview
    assert 'tls_payload' not in overview
    compact_copy = 'Review TLS lifecycle, Ingress coverage, and governed rotation.'
    assert len(compact_copy) <= 65
    assert f"'description': '{compact_copy}'" in overview
    assert "'supporting': capability.boundary" not in overview
    assert '{{ capability.boundary }}' not in overview
    assert "'boundary':" not in overview
    assert "'title': 'Internal Certificates'" in overview
    assert 'workspace.status_tone|default(none)' in shared_card
    assert "workspace.action_label|default('Open Workspace', true)" in shared_card

    assert 'Governance Overview landing contract' in standard
    assert 'domain-first' in standard
    assert 'get_tls_collection_snapshot()' in standard
    assert 'TLS Collection Snapshot' in standard
    assert '**Open Cluster Integrations**' in standard
    assert 'scalable equal-height catalog' in standard
    assert 'parent section owns no TLS-specific action' in standard
    assert 'two-column grid' in standard


def test_tls_snapshot_copy_posture_badge_and_search_follow_shared_inventory_patterns() -> None:
    service = read('app/kubernetes/governance/tls_certificates/service.py')
    snapshot_partial = read('app/templates/kubernetes/governance/tls_certificates/partials/_snapshot_context.html')
    posture = read('app/templates/kubernetes/governance/tls_certificates/partials/_summary_cards.html')
    filters = read('app/templates/kubernetes/governance/tls_certificates/partials/_filters.html')
    inventory = read('app/templates/kubernetes/inventory/nodes/partials/_summary_cards.html')

    description = 'TLS certificates and Ingress host mappings.'
    assert len(description) <= 48
    assert f"'description': '{description}'" in service
    assert "'source_label': 'Kubernetes TLS Secrets + Ingresses'" in service
    assert 'payload.snapshot.description' in snapshot_partial
    assert 'components/resource_posture_grid.html' in posture
    assert 'components/table_label.html' in posture
    assert "table_label.metadata_label(metrics|length ~ ' Indicators', icon='layout-grid')" in posture
    assert 'header_badge=posture_badge' in posture
    assert 'posture_grid.render(metrics, columns=3)' in posture
    assert "table_label.metadata_label(posture_metrics|length ~ ' Indicators', icon='layout-grid')" in inventory
    assert "'Search certificates...'" in filters
    assert "table_ui.search_field('search'," in filters
    assert "id='tls-search-filter'" in filters
    assert 'Search Secret name, namespace, subject, or issuer' not in filters


def test_internal_pki_source_readiness_is_a_real_authorized_navigation_workspace() -> None:
    routes = read('app/kubernetes/governance/routes.py')
    child = read('app/kubernetes/governance/internal_certificates/routes.py')
    service = read('app/kubernetes/governance/internal_certificates/service.py')
    overview = read('app/templates/kubernetes/governance/overview/index.html')
    workspace = read('app/templates/kubernetes/governance/internal_certificates/index.html')
    access = read('app/definitions/catalogs/access/rbac/access.yaml')

    assert "@permission_required('governance.view')" in child
    assert "@permission_required('clusters.view')" in child
    assert "@permission_required('internal_certificates.view')" in child
    assert 'if registered_clusters is True else None' in child
    assert routes.index('can_view_internal_certificates = current_user.has_permission(') < routes.index(
        'can_view_internal_certificates=can_view_internal_certificates'
    )
    assert "endpoint='internal_certificates'" in routes
    assert 'view_func=internal_certificates_index' in routes
    assert "current_user.has_permission('clusters.view')" in routes
    assert "'title': 'Internal Certificates'" in overview
    assert "'status': 'Source Pending'" in overview
    assert "url_for('governance.internal_certificates')" in overview
    assert "'available': can_view_internal_certificates" in overview
    assert "'title': 'TLS Certificates'" in overview
    assert 'sm:grid-cols-2' in overview
    assert 'capability.search_text' in overview
    assert 'workspace_card.render(' in overview

    navigation_catalog = read('app/common/workspace_navigation_catalog.py')
    navigation = read('app/common/workspace_navigation.py')
    navigation_standard = read('docs/design/components/DOMAIN_WORKSPACE_NAVIGATION.md')
    assert "'governance.internal_certificates'" in navigation_catalog
    assert "'internal_certificates.view'" in navigation_catalog
    assert "'governance.internal_certificates': 'internal_certificates'" in navigation
    assert "view.endpoint != 'governance.internal_certificates'" in navigation
    assert "user.has_permission('clusters.view')" in navigation
    assert 'Overview · TLS Certificates · Internal Certificates' in navigation_standard

    assert 'permission_dependencies:' in access
    assert 'internal_certificates.view: [governance.view, clusters.view]' in access
    assert '- key: internal_certificates.view' in access
    assert access.count('  - internal_certificates.view') == 5

    assert 'View PKI Evidence' in workspace
    assert "url_for('governance.internal_certificates', cluster_id=record.id)" in workspace
    assert "'cluster_id': payload.selected_cluster_id" in workspace
    assert 'Clear Cluster Scope' in workspace

    assert 'db.session.execute(' in service
    assert 'KubernetesConnection.detected_platform' in service
    assert 'KubernetesConnection.detected_version' in service
    assert 'select(func.count(Cluster.id))' in service
    assert 'KubernetesConnection.kubeconfig,' not in service
    assert 'Cluster.kubernetes_connection' not in service
    assert 'Cluster.name.ilike' in service
    assert '_DEFAULT_PER_PAGE = 5' in service
    assert "'collection_status': 'Not Collected'" in service
    assert "'authority_status': 'Not Verified'" in service
    assert "'expiry_status': 'Unknown'" in service
    assert 'get_integration(' not in service
    assert 'get_tls_certificate_page(' not in service
    assert 'kubeadm certs renew' not in service

    assert 'Internal PKI Source Registry' in workspace
    assert "registry_ui.filter_form('governance.internal_certificates'" in workspace
    assert "registry_ui.footer('governance.internal_certificates'" in workspace
    assert 'components/resource_posture_grid.html' in workspace
    assert 'components/info_tip.html' in workspace
    assert 'Not Collected' in workspace
    assert 'Not Verified' in workspace
    assert 'Renewal Deferred' in workspace
    assert 'Collection source not configured' in workspace
    assert 'Automated PKI Collection Pending' in workspace
    assert 'Request Renewal' not in workspace
    assert 'Rotate All' not in workspace


def test_internal_pki_certificate_registry_uses_committed_attested_evidence_only() -> None:
    route = read('app/kubernetes/governance/internal_certificates/routes.py')
    service = read('app/kubernetes/governance/internal_certificates/service.py')
    readiness = read('app/kubernetes/governance/internal_certificates/readiness.py')
    importer = read('app/kubernetes/governance/internal_certificates/evidence_import.py')
    commands = read('app/commands/__init__.py')
    cli = read('app/commands/internal_pki.py')
    model = read('app/models/internal_certificates.py')
    migration = read('migrations/versions/20261112_internal_pki_evidence.py')
    template = read('app/templates/kubernetes/governance/internal_certificates/index.html')
    partial = read('app/templates/kubernetes/governance/internal_certificates/partials/_certificate_inventory.html')

    assert 'get_internal_certificate_inventory_page(request.args)' in route
    assert 'check_internal_pki_schema_readiness()' in route
    assert 'schema_readiness.ready' in route
    assert 'get_internal_certificate_inventory_page' in service
    assert 'committed_count = select(func.count(InternalPKICertificateInventory.id))' in service
    assert 'committed_count.where(InternalPKICertificateInventory.cluster_id == cluster_id)' in service
    assert 'InternalPKICertificateInventory.query' in service
    assert 'InternalPKIEvidenceBatch' in service
    assert 'source_rows = db.session.execute(' in service
    assert 'func.max(InternalPKIEvidenceBatch.collected_at)' in service
    assert "source_label': 'Operator Attested'" in service
    assert 'def _expiry_presentation(' in service
    assert '_DEFAULT_PER_PAGE = 5' in service
    assert "INTERNAL_PKI_REVISION = '20261112_internal_pki'" in readiness
    assert 'inspect(db.engine).get_table_names()' in readiness

    assert "SCHEMA_VERSION = 'kaori.internal-pki-evidence.v1'" in importer
    assert 'MAX_MANIFEST_BYTES = 128 * 1024' in importer
    assert 'MAX_RECORDS = 100' in importer
    assert 'manifest_sha256' in importer
    assert 'db.session.commit()' in importer
    assert 'AuditEvent(' in importer
    assert 'kubeadm_check_expiration' in importer
    assert 'db.session.get(Cluster,' in importer
    assert 'import_internal_pki' in commands
    assert 'import-internal-pki' in cli
    adapter = read('app/kubernetes/governance/internal_certificates/kubeadm_adapter.py')
    assert 'def prepare_kubeadm_metadata_manifest(' in adapter
    assert "_SUPPORTED_VERSION = 'v1.36.4'" in adapter
    assert "_SOURCE_API_VERSION = 'output.kubeadm.k8s.io/v1alpha3'" in adapter
    assert 'validate_metadata_manifest(manifest)' in adapter
    assert 'prepare-internal-pki' in cli
    assert 'os.O_EXCL' in cli
    assert '0o600' in cli
    assert 'app.cli.add_command(prepare_internal_pki)' in commands
    assert 'MAX_MANIFEST_BYTES + 1' in cli
    assert 'InternalPKICertificateInventory' in model
    assert 'InternalPKIEvidenceBatch' in model
    assert 'op.create_table(' in migration
    assert 'op.drop_table(' in migration

    assert "section_intro.render('Source Readiness'" not in template
    assert 'aria-label="Internal PKI source readiness"' in template
    assert 'PKI Evidence Boundaries' in template
    assert 'partials/_certificate_inventory.html' in template
    assert 'inventory.committed_total' in template
    assert 'inventory.total' in partial
    assert 'Internal Certificate Registry' in partial
    assert "registry_ui.filter_form('governance.internal_certificates'" in partial
    assert "registry_ui.footer('governance.internal_certificates'" in partial
    assert "page_param='cert_page'" in partial
    assert 'cert_per_page' in partial
    assert 'Operator Attested' in partial
    assert 'Installed status unverified' in partial
    assert 'Request Renewal' not in partial
    assert 'Rotate All' not in partial
    for forbidden in ('core_api(', 'list_certificate_signing_request(', 'subprocess.', 'paramiko', 'ssh '):
        assert forbidden not in importer
        assert forbidden not in service


def test_internal_pki_devcontainer_migration_uses_existing_privileged_handoff() -> None:
    pki_runbook = read('docs/design/patterns/KUBERNETES_INTERNAL_CERTIFICATES_EVIDENCE_IMPORT.md')
    canonical_runbook = read('docs/operations/devcontainer-postgres-first-run.md')
    migration_runner = read('scripts/devcontainer/bootstrap-db.sh')
    role_contract = read('tests/contracts/release/test_devcontainer_postgres_runtime_role_contract.py')

    command = (
        'docker compose -f compose.yml -f .devcontainer/compose.devcontainer.yml '
        'run --rm db-bootstrap sh scripts/devcontainer/bootstrap-db.sh --upgrade-only'
    )
    assert command in pki_runbook
    assert command in canonical_runbook
    assert 'KAORI_DB_MIGRATION_URL' in migration_runner
    assert 'kaori_migrator' in migration_runner
    assert 'grant_postgres_runtime.sql' in migration_runner
    assert 'flask --app run:app seed-rbac' in migration_runner
    assert 'test_devcontainer_operator_bootstrap_orders_schema_grants_and_app_admin' in role_contract
    assert 'Do NOT run `flask db upgrade` with the restricted workspace DATABASE_URL.' in pki_runbook
    assert 'GRANT USAGE, CREATE ON SCHEMA public TO approved_kaori_migration_role' not in pki_runbook


def test_governance_dead_job_presentation_helper_is_retired() -> None:
    source = read('app/kubernetes/governance/tls_certificates/job_presentation.py')
    assert 'def get_active_tls_sync_job(' not in source


def test_governance_final_release_evidence_is_wired_to_quality_gate() -> None:
    quality_gate = read('scripts/quality_gate.sh')
    coverage = read('scripts/verify_feature_test_coverage.py')
    assert 'python scripts/verify_governance_final_lock.py' in quality_gate
    for path in (
        'tests/unit/kubernetes/governance/test_tls_governance_policy.py',
        'tests/kubernetes/governance/test_tls_governance_route_characterization.py',
        'tests/security/kubernetes/governance/test_tls_governance_security.py',
        'tests/rendering/kubernetes/governance/test_tls_governance_rendering.py',
        'tests/integration/kubernetes/governance/test_tls_certificate_read_model.py',
        'tests/e2e/kubernetes/governance/test_tls_governance_smoke.py',
    ):
        assert path in coverage
