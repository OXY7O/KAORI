from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / 'app/templates/integrations/jobs.html'
REGISTRY = ROOT / 'app/templates/integrations/jobs/partials/_registry.html'
PRESENTATION = ROOT / 'app/jobs/presentation.py'
README = ROOT / 'app/jobs/README.md'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_jobs_hero_uses_canonical_typography_and_compact_context_panel() -> None:
    page = read(PAGE)
    assert 'page_hero.title_classes()' in page
    assert 'page_hero.description_classes()' in page
    assert 'page_hero.metadata_row_classes()' in page
    assert page.count('page_hero.context_metric(') == 2
    assert 'page_hero.supporting_strip' not in page
    assert 'Monitor queued, running, and completed work across KAORI worker pools.' in page
    assert 'Worker Queue Readiness' in page


def test_job_rows_receive_workload_icons() -> None:
    presentation = read(PRESENTATION)
    registry = read(REGISTRY)
    for icon in ('activity', 'scan-search', 'chart-no-axes-combined', 'chart-spline', 'workflow'):
        assert f"'{icon}'" in presentation
    assert "'icon': _JOB_ICONS.get" in presentation
    assert 'data-lucide="{{ row.icon }}"' in registry


def test_job_retention_boundary_is_documented_separately_from_activity_audit() -> None:
    text = read(README)
    assert 'Job records and Activity Audit records are different' in text
    assert 'separate `job_execution` domain' in text
    assert 'active jobs: never eligible' in text
    assert 'must not enable ad-hoc database deletion scripts' in text
