from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def test_reveal_registries_use_one_canonical_sql_paging_policy() -> None:
    source = (ROOT / 'app/kubernetes/operations/secrets/reveal_service.py').read_text()
    body = source.split('def get_reveal_page_context(', 1)[1].split('def create_reveal_request(', 1)[0]
    assert 'pending_per_page: int = 5' in body
    assert 'my_requests, my_window = paginate_query(' in body
    assert 'pending_requests, pending_window = paginate_query(' in body
    assert 'build_pagination_window(' in body
    assert "my_window['total_items']" in body
    assert "pending_window['total_items']" in body
    assert "'page_sizes': PER_PAGE_OPTIONS" in body
    assert 'pending_page_sizes = (3, 5, 10)' not in body


def test_reveal_route_preserves_separate_htmx_windows() -> None:
    routes = (ROOT / 'app/kubernetes/operations/secrets/reveal_routes.py').read_text()
    assert "my_per_page=request.args.get('my_per_page', 5, type=int) or 5" in routes
    assert "pending_per_page=request.args.get('pending_per_page', 5, type=int) or 5" in routes
