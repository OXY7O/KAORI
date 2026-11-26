from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / 'app/templates'
PARTIALS = TEMPLATES / 'intelligence/partials'


def _render_empty(
    status: str,
    *,
    runtime_status: str = 'not_materialized',
    filter_count: int = 0,
    allowed: bool = True,
) -> str:
    environment = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)
    template = environment.get_template('intelligence/partials/_recommendation_records.html')
    return template.render(
        payload={
            'items': [],
            'active_filter_count': filter_count,
            'evidence_readiness': {'status': status},
            'registry_runtime_evidence': {
                'status': runtime_status,
                'title': 'Runtime Correlation Required',
                'description': 'Run the registered correlation job before interpreting absent findings.',
            },
        },
        url_for=lambda _endpoint: '/artifact-registry/runtime',
        current_user=SimpleNamespace(
            has_permission=lambda permission: allowed and permission == 'artifact_registry.view',
        ),
    )


def test_missing_runtime_evidence_is_one_actionable_empty_state() -> None:
    html = _render_empty('partial')
    assert html.count('data-kaori-empty-state') == 1
    assert 'Runtime Correlation Required' in html
    assert 'Review Runtime Usage' in html
    assert 'Recent inventory or evaluation coverage is also incomplete.' in html
    assert 'No Active Recommendations' not in html
    assert '/artifact-registry/runtime' in html


def test_evaluator_failure_and_filter_context_are_not_overwritten() -> None:
    failed = _render_empty('unavailable')
    assert 'Recommendation Evaluation Unavailable' in failed
    assert 'Runtime Correlation Required' in failed
    assert 'Review Runtime Usage' in failed
    filtered = _render_empty('baseline_recent', filter_count=1)
    assert 'No Recommendations Match the Current Filters' in filtered
    assert 'Runtime Correlation Required' in filtered
    assert 'Review Runtime Usage' in filtered


def test_ready_evidence_and_unauthorized_cta() -> None:
    ready = _render_empty('baseline_recent', runtime_status='ready')
    assert 'No Active Recommendations From Current Evidence' in ready
    assert 'Review Runtime Usage' not in ready
    denied = _render_empty('partial', allowed=False)
    assert 'Runtime Correlation Required' in denied
    assert 'Review Runtime Usage' not in denied


def test_alert_metadata_guide_and_scoped_vault_boundary() -> None:
    summary = (PARTIALS / '_alert_intelligence_summary.html').read_text(encoding='utf-8')
    workspace = (PARTIALS / '_alert_intelligence_workspace.html').read_text(encoding='utf-8')
    overview = (PARTIALS / '_alert_ops_overview.html').read_text(encoding='utf-8')
    assert "metadata_label('4 Indicators', icon='layout-dashboard')" in summary
    assert 'title_extra=summary_title_label' in summary
    assert "variant='guide'" in workspace
    assert 'title_extra=workspace_guide' in workspace
    assert 'Ownership Boundary' in workspace
    assert 'not payload.snapshot.available' in workspace
    assert 'Committed Evidence Review Required' in workspace
    assert 'payload.snapshot.serving_last_good' in workspace
    assert 'Last Good Snapshot Active' in workspace
    assert 'operational_callout.render' not in overview
    assert 'Delivery and archive readiness.' in overview
    assert 'Closure may be pending.' in overview
    assert 'alert_intelligence.vault_cases' not in workspace
    routes = (ROOT / 'app/intelligence/alert_intelligence/routes.py').read_text(encoding='utf-8')
    assert "@alert_intelligence_bp.get('/vault-cases')" in routes
    assert "@alert_intelligence_bp.get('/vault-cases/<string:public_id>/details')" in routes
