from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_runtime_correlation_uses_committed_kubernetes_inventory() -> None:
    correlation = (ROOT / 'app/artifact_registry/correlation.py').read_text()
    assert 'PodInventory' in correlation
    assert 'container_images' in correlation
    assert 'KubernetesClient' not in correlation
    assert 'requests.' not in correlation


def test_digest_match_is_stronger_than_tag_match() -> None:
    correlation = (ROOT / 'app/artifact_registry/correlation.py').read_text()
    digest_index = correlation.index("return 'digest', 'strong'")
    tag_index = correlation.index("return 'tag', 'medium'")
    assert digest_index < tag_index


def test_runtime_correlation_is_bounded_atomic_and_progress_aware() -> None:
    correlation = (ROOT / 'app/artifact_registry/correlation.py').read_text()
    task = (ROOT / 'app/artifact_registry/correlation_tasks.py').read_text()

    assert 'with Session(db.engine) as materialization_session' in correlation
    assert 'materialization_session.begin()' in correlation
    assert 'materialization_session.query(PodInventory)' in correlation
    assert '.yield_per(normalized_batch_size)' in correlation
    assert 'insert(RegistryWorkloadBinding)' in correlation
    assert 'pending_bindings.clear()' in correlation
    assert 'progress_callback(' in correlation
    assert 'digest_index' in correlation
    assert 'tag_index' in correlation
    assert 'selectinload(RegistryArtifact.tags)' in correlation
    assert 'by_path.get(image.repository' not in correlation
    assert 'filter_current_generation(PodInventory.query, PodInventory)' not in correlation
    assert 'progress_callback=report_correlation_progress' in task
    assert 'self.update_state(' in task
    assert "state='PROGRESS'" in task
    assert "stage='Materializing Runtime Correlation'" in task


def test_runtime_usage_is_cross_domain_canonical_workspace() -> None:
    presentation = (ROOT / 'app/artifact_registry/presentation_runtime.py').read_text()
    routes = (ROOT / 'app/artifact_registry/routes.py').read_text()
    page = (ROOT / 'app/templates/artifact_registry/runtime.html').read_text()
    workspace = (ROOT / 'app/templates/artifact_registry/partials/_runtime_workspace.html').read_text()
    detail = (ROOT / 'app/templates/artifact_registry/partials/_runtime_binding_detail.html').read_text()

    assert 'def build_runtime_usage(' in presentation
    assert 'paginate_query(' in presentation
    assert "'All Registry Sources'" in presentation
    assert "'All Kubernetes Clusters'" in presentation
    assert 'RegistryWorkloadBinding.query.join(' in presentation
    assert 'RegistryWorkloadBinding.image_reference' in presentation
    assert 'RegistryWorkloadBinding.artifact_id == int(request.artifact_id)' in presentation
    assert "'security_exposed': counts['security_exposed']" in presentation
    assert 'def build_runtime_binding_detail(binding_id: int)' in presentation

    assert "request.args.get('source_id', type=int)" in routes
    assert "request.args.get('cluster_id', '', type=str)" in routes
    assert "request.args.get('namespace', '', type=str)" in routes
    assert "request.args.get('match_type', '', type=str)" in routes
    assert "request.args.get('exposure', '', type=str)" in routes
    assert "request.args.get('artifact_id', type=int)" in routes
    assert "@artifact_registry_bp.get('/runtime/<int:binding_id>/details')" in routes

    assert 'artifact_registry/partials/_runtime_workspace.html' in page
    assert 'resource_detail_modal.inventory_host(' in page
    assert 'Correlation Snapshot' in workspace
    assert 'Runtime Bindings' in workspace
    assert 'Digest Matched' in workspace
    assert 'Tag Matched' in workspace
    assert 'Security Exposed' in workspace
    assert 'name="source_id"' in workspace
    assert 'name="cluster_id"' in workspace
    assert 'name="namespace"' in workspace
    assert 'name="match_type"' in workspace
    assert 'name="exposure"' in workspace
    assert 'table_ui.inventory_block_header' in workspace
    assert 'registry.footer(' in workspace
    assert '[5, 10, 25, 50]' in workspace
    assert 'resource_detail_modal.detail_button(' in workspace

    assert 'data-kaori-detail-variant="full-workspace-modal"' in detail
    assert 'Artifact Identity' in detail
    assert 'Registry Provenance' in detail
    assert 'Runtime Target' in detail
    assert 'Correlation Evidence' in detail
    assert 'Security Exposure' in detail
    assert 'Committed Artifact Registry and Kubernetes inventory only' in detail


def test_runtime_usage_keeps_committed_snapshot_readable_when_refresh_is_unavailable() -> None:
    presentation = (ROOT / 'app/artifact_registry/presentation_runtime.py').read_text()
    workspace = (ROOT / 'app/templates/artifact_registry/partials/_runtime_workspace.html').read_text()

    assert 'def _runtime_prerequisite_guidance(' in presentation
    assert "'is_blocked': bool(not eligible and not has_committed_snapshot)" in presentation
    assert "'refresh_blocked': bool(not eligible and has_committed_snapshot)" in presentation
    assert "'Kubernetes Inventory Required'" in presentation
    assert "action_endpoint = 'inventory.overview'" in presentation
    assert "status, tone, description = 'Refresh Unavailable', 'warning', setup['refresh_description']" in presentation
    assert 'has_committed_snapshot=latest_correlated_at is not None' in presentation

    assert '{% if runtime.setup.refresh_blocked %}' not in workspace
    assert 'Refresh Blocked' not in workspace
    assert 'Committed Inventory Required' not in workspace


def test_runtime_usage_preserves_digest_first_and_explicit_tag_confidence() -> None:
    presentation = (ROOT / 'app/artifact_registry/presentation_runtime.py').read_text()
    workspace = (ROOT / 'app/templates/artifact_registry/partials/_runtime_workspace.html').read_text()

    assert "'description': 'Immutable digest identity match.'" in presentation
    assert "'description': 'Mutable reference; lower confidence.'" in presentation
    assert "'tone': 'warning'" in presentation
    assert 'row.match.description' in workspace


def test_runtime_summary_reuses_shared_section_intro_and_grouped_metrics() -> None:
    from jinja2 import Environment

    template = (ROOT / 'app/templates/artifact_registry/partials/_runtime_workspace.html').read_text()
    Environment().parse(template)
    start = template.index("section_intro.render('Runtime Correlation',")
    end = template.index("section_intro.render('Runtime Bindings',", start)
    summary = template[start:end]

    assert 'artifact-registry-runtime-summary-heading' in template
    assert 'section_card.render(' in summary
    assert "'Runtime Evidence Summary'" in summary
    assert "body_classes='p-0'" in summary
    assert 'posture_grid.render(runtime_metrics, columns=4)' in summary
    for name in ('Runtime Bindings', 'Digest Matched', 'Tag Matched', 'Security Exposed'):
        assert name in summary
    assert "'warning' if runtime.tag_matches else 'info'" in summary
    assert "'critical' if runtime.security_exposed else 'info'" in summary
    assert 'metric_card.render(' not in summary
    assert 'registry.footer(' in template
