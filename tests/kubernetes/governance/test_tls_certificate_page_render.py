from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[3]


def _payload() -> SimpleNamespace:
    return SimpleNamespace(
        summary=SimpleNamespace(
            total=4,
            healthy=3,
            warning=1,
            critical=0,
            expired=0,
            invalid=0,
            unknown=0,
            coverage_full=3,
            coverage_partial=1,
            coverage_uncovered=0,
            coverage_none=0,
            coverage_not_reported=0,
            issuer_count=2,
        ),
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
        status_options=('all', 'healthy', 'warning', 'critical'),
        validity_policy=SimpleNamespace(renewal_window_days=30, critical_window_days=7),
        snapshot=SimpleNamespace(scope_label='All Clusters'),
    )


def test_tls_summary_renders_with_canonical_inventory_component() -> None:
    environment = Environment(
        loader=FileSystemLoader(ROOT / 'app' / 'templates'),
        autoescape=select_autoescape(['html', 'xml']),
    )
    environment.globals['url_for'] = lambda endpoint, **values: f'/{endpoint}'

    current_user = SimpleNamespace(has_permission=lambda _permission: False)
    rendered = environment.get_template('kubernetes/governance/tls_certificates/partials/_summary_cards.html').render(
        payload=_payload(), current_user=current_user
    )

    assert 'Certificate Validity' in rendered
    assert 'Certificate Validity &amp; Operations' not in rendered
    assert 'Certificate Validity & Operations' not in rendered
    assert 'TLS Inventory Operations' not in rendered
    assert 'Renewal Window' in rendered
    assert 'Host Coverage Exceptions' in rendered


def test_tls_page_does_not_load_retired_request_progress_toast_script() -> None:
    index = (ROOT / 'app/templates/kubernetes/governance/tls_certificates/index.html').read_text()

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
    environment.globals['request'] = SimpleNamespace(view_args={})

    rendered = environment.get_template('kubernetes/governance/tls_certificates/partials/_table.html').render(
        payload=_payload()
    )

    assert 'aria-label="Rows Per Page"' in rendered
    assert 'data-kaori-numeric-pagination' in rendered
    assert 'data-current-page="2"' in rendered
    assert 'data-total-pages="5"' in rendered
    assert 'href="/governance.tls_certificates?' in rendered
    assert 'hx-get="/governance.tls_certificates?' in rendered
    assert 'partial_mode=table' in rendered


def test_bulk_tls_target_table_uses_inventory_pagination_contract() -> None:
    environment = Environment(
        loader=FileSystemLoader(ROOT / 'app' / 'templates'),
        autoescape=select_autoescape(['html', 'xml']),
    )
    environment.filters['environment_name'] = lambda value, empty='Environment not specified': value or empty

    def url_for(endpoint: str, **values: object) -> str:
        query = urlencode(values)
        return f'/{endpoint}' + (f'?{query}' if query else '')

    environment.globals['url_for'] = url_for
    environment.globals['request'] = SimpleNamespace(view_args={})

    rendered = environment.get_template('kubernetes/operations/secrets/_bulk_target_table.html').render(
        payload=_payload(), selected_ids=[]
    )

    assert 'id="tls-secret-update-target-table"' in rendered
    assert 'data-kaori-numeric-pagination' in rendered
    assert 'data-current-page="2"' in rendered
    assert 'data-total-pages="5"' in rendered
    assert 'aria-label="Rows Per Page"' in rendered
    assert 'href="/kubernetes_operations.tls_secret_bulk_rotation?' in rendered
    assert 'hx-get="/kubernetes_operations.tls_secret_bulk_rotation?' in rendered
    assert 'partial_mode=bulk_table' in rendered


def test_numeric_pagination_rerenders_after_outer_html_swaps() -> None:
    script = (ROOT / 'app/static/js/pagination.js').read_text()

    assert "document.addEventListener('htmx:afterSwap', renderAfterHtmxSwap)" in script
    assert "document.addEventListener('htmx:afterSettle', renderAfterHtmxSwap)" in script
    assert 'target && target.isConnected' in script
    assert 'renderAll(document)' in script


def test_tls_registry_compact_copy_distinguishes_observed_zero_and_unreported() -> None:
    environment = Environment(
        loader=FileSystemLoader(ROOT / 'app' / 'templates'),
        autoescape=select_autoescape(['html', 'xml']),
    )
    environment.filters['user_date'] = lambda value, *args: '24 Dec 2026'
    environment.filters['environment_name'] = lambda value, empty='Environment not specified': value or empty

    def url_for(endpoint: str, **values: object) -> str:
        query = urlencode(values)
        return f'/{endpoint}' + (f'?{query}' if query else '')

    environment.globals['url_for'] = url_for
    environment.globals['request'] = SimpleNamespace(view_args={})

    def record(record_id: int, *, reported: bool) -> SimpleNamespace:
        return SimpleNamespace(
            id=record_id,
            cluster=None,
            cluster_id='cluster-1',
            namespace='capsule-system',
            secret_name=f'capsule-tls-{record_id}',
            common_name=None,
            not_after='2026-12-24',
            status='healthy',
            days_remaining=74,
            parse_error=None,
            declared_host_count=0,
            covered_host_count=0,
            uncovered_hosts=[],
            presentation={
                'status_label': 'Valid',
                'status_tone': 'normal',
                'validity_days_remaining': 74,
                'validity_status': 'healthy',
                'coverage_label': 'No Declared Hosts' if reported else 'Not Reported',
                'coverage_tone': 'info' if reported else 'unknown',
                'coverage_reported': reported,
                'ingress_mapping_reported': reported,
                'ingress_consumer_count': 0 if reported else None,
                'declared_host_count': 0 if reported else None,
            },
        )

    payload = _payload()
    payload.records = (record(1, reported=True), record(2, reported=False))
    rendered = environment.get_template('kubernetes/governance/tls_certificates/partials/_table.html').render(
        payload=payload
    )

    assert rendered.count('No Declared Hosts') == 1
    assert 'Coverage evidence unavailable' in rendered
    assert 'Ingress mapping unavailable' in rendered
    assert '0 Ingresses' in rendered
    assert '74 days left' in rendered
    assert '0 Declared Hosts' not in rendered
    assert '24 Dec 2026' in rendered
