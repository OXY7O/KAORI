from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

from jinja2 import Environment, FileSystemLoader, select_autoescape


ROOT = Path(__file__).resolve().parents[2]


def _payload() -> SimpleNamespace:
    return SimpleNamespace(
        summary=SimpleNamespace(total=4, healthy=3, warning=1, critical=0, expired=0, invalid=0),
        sync_state=SimpleNamespace(
            label='Current',
            tone='normal',
            is_active=False,
            helper='TLS certificate inventory is current.',
            automatic_enabled=True,
            last_success_label='26 Jul 2026, 10:00',
            next_run_label='In 5 Hours',
            active_job_public_id=None,
            progress_message=None,
            progress_percent=100,
        ),
        filters=SimpleNamespace(cluster_id='', namespace='', status='', search=''),
        pagination=SimpleNamespace(
            page=2,
            per_page=5,
            allowed_per_page=(5, 10, 25, 50),
            start_item=6,
            end_item=10,
            total_items=24,
            total_pages=5,
            has_prev=True,
            prev_page=1,
            has_next=True,
            next_page=3,
        ),
        records=(),
        clusters=(),
        namespaces=(),
        status_options=('', 'healthy', 'warning', 'critical'),
    )


def test_tls_summary_renders_with_canonical_inventory_component() -> None:
    environment = Environment(
        loader=FileSystemLoader(ROOT / 'app' / 'templates'),
        autoescape=select_autoescape(['html', 'xml']),
    )
    environment.globals['url_for'] = lambda endpoint, **values: f'/{endpoint}'

    rendered = environment.get_template(
        'governance/tls_certificates/partials/_summary_cards.html'
    ).render(payload=_payload())

    assert 'Certificate Coverage and Readiness' in rendered
    assert 'TLS Inventory Operations' in rendered
    assert 'Current' in rendered


def test_tls_page_does_not_load_retired_request_progress_toast_script() -> None:
    index = (
        ROOT / 'app/templates/governance/tls_certificates/index.html'
    ).read_text()

    assert 'tls_certificate_management.js' not in index
    assert not (ROOT / 'app/static/js/tls_certificate_management.js').exists()

def test_tls_pagination_uses_inventory_navigation_contract() -> None:
    environment = Environment(
        loader=FileSystemLoader(ROOT / 'app' / 'templates'),
        autoescape=select_autoescape(['html', 'xml']),
    )
    environment.filters['user_date'] = lambda value: value or '-'
    environment.filters['environment_name'] = lambda value, empty='Environment not specified': value or empty

    def url_for(endpoint: str, **values: object) -> str:
        query = urlencode(values)
        return f'/{endpoint}' + (f'?{query}' if query else '')

    environment.globals['url_for'] = url_for

    rendered = environment.get_template(
        'governance/tls_certificates/partials/_table.html'
    ).render(payload=_payload())

    assert 'aria-label="Rows Per Page"' in rendered
    assert 'data-kaori-numeric-pagination' in rendered
    assert 'data-current-page="2"' in rendered
    assert 'data-total-pages="5"' in rendered
    assert 'href="/governance.tls_certificates?' in rendered
    assert 'hx-get="/governance.tls_certificates?' in rendered
    assert 'partial_mode=inventory_scope' in rendered

