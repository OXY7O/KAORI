from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / 'app' / 'templates'


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_top_consumers_payload_declares_and_checks_schema_version() -> None:
    contracts = read('app/analytics/top_consumers/contracts.py')
    domain = read('app/analytics/top_consumers/domain.py')
    presentation = read('app/analytics/top_consumers/presentation.py')

    assert 'TOP_CONSUMERS_PAYLOAD_SCHEMA_VERSION = 3' in contracts
    assert "'schema_version': TOP_CONSUMERS_PAYLOAD_SCHEMA_VERSION" in domain
    assert 'def is_current_payload(payload: Any) -> bool:' in domain
    assert 'if not is_current_payload(payload):' in presentation
    assert 'Run Refresh/Materialize Top Consumers' in presentation


def test_top_consumers_hero_handles_legacy_payload_without_scope() -> None:
    environment = Environment(
        loader=FileSystemLoader(TEMPLATES),
        undefined=StrictUndefined,
    )
    template = environment.get_template('analytics/top_consumers/partials/_hero.html')

    rendered = template.render(
        payload={'summary': {}, 'rows': []},
        selected_cluster_name='K8s PGN Staging',
        dependency_blocker=None,
        total_rows=0,
        recommendation_count=0,
    )

    assert 'Top Consumers' in rendered
    assert 'Cluster' in rendered
    assert '0 of 4 Resources Complete' in rendered


def test_top_consumers_summary_handles_missing_nested_payload_fields() -> None:
    environment = Environment(
        loader=FileSystemLoader(TEMPLATES),
        undefined=StrictUndefined,
    )
    template = environment.get_template('analytics/top_consumers/partials/_summary.html')

    rendered = template.render(payload={})

    assert 'Top Consumer Summary' in rendered
    assert 'N/A' in rendered
    assert 'Unknown' in rendered
