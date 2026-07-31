from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / 'app' / 'templates'


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_top_consumers_payload_declares_and_checks_schema_version() -> None:
    source = read('app/analytics/top_consumers/service.py')

    assert 'TOP_CONSUMERS_PAYLOAD_SCHEMA_VERSION = 2' in source
    assert "'schema_version': TOP_CONSUMERS_PAYLOAD_SCHEMA_VERSION" in source
    assert 'def is_current_top_consumers_payload(payload: Any) -> bool:' in source
    assert 'if not is_current_top_consumers_payload(payload):' in source
    assert 'Run Refresh/Materialize Top Consumers' in source


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
