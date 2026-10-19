from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def test_reveal_registries_use_one_canonical_sql_paging_policy() -> None:
    source = (ROOT / 'app/kubernetes/operations/secrets/reveal_service.py').read_text()
    body = source.split('def get_reveal_page_context(', 1)[1].split('def create_reveal_request(', 1)[0]
    assert 'pending_pagination: PendingRevealPagination = PendingRevealPagination()' in body
    assert 'class PendingRevealPagination:' in source
    assert 'per_page: int = 5' in source
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
    assert 'pending_pagination=PendingRevealPagination(' in routes
    assert "per_page=request.args.get('pending_per_page', 5, type=int) or 5" in routes


def test_review7_my_requests_uses_sql_filters_with_requester_isolation() -> None:
    service = (ROOT / 'app/kubernetes/operations/secrets/reveal_service.py').read_text()
    block = service.split('def get_reveal_page_context(', 1)[1].split('def create_reveal_request(', 1)[0]
    assert 'my_search: str' in block
    assert 'my_status: str' in block
    assert 'my_sort: str' in block
    assert 'SecretRevealRequest.query.filter_by(requester_user_id=user_id)' in block
    assert 'autoescape=True' in block
    assert 'SecretRevealRequest.status == state_filter' in block
    assert 'SecretRevealRequest.requested_at.asc()' in block
    assert 'SecretRevealRequest.requested_at.desc()' in block
    assert 'if state_filter not in allowed_statuses' in block
    assert "'my_reveal_filters':" in block


def test_review7_my_requests_uses_canonical_filter_loading_table_and_footer() -> None:
    source = (ROOT / 'app/templates/kubernetes/operations/secrets/_reveal_request_status.html').read_text()
    routes = (ROOT / 'app/kubernetes/operations/secrets/reveal_routes.py').read_text()
    assert "table_registry.filter_form('kubernetes_operations.reveal_secret'" in source
    assert "table_registry.footer('kubernetes_operations.reveal_secret'" in source
    assert "table_registry.clear_filters_link('kubernetes_operations.reveal_secret'" in source
    assert 'table_ui.table_classes(' in source
    assert 'table_ui.head_classes()' in source
    assert 'table_ui.body_classes()' in source
    assert 'table_ui.row_classes()' in source
    assert "loading_bar.render('my-secret-reveal-loading'" in source
    assert 'scope="col"' in source
    assert 'No Matching Reveal Requests' in source
    assert 'name="my_status"' in source
    assert 'name="my_sort"' in source
    assert "table_ui.search_field('my_search'" in source
    assert 'my_search=my_reveal_filters.search' in source
    assert "page_param='my_page'" in source
    assert "per_page_param='my_per_page'" in source
    assert "name='reveal_view'" not in source
    assert 'value="mine"' in source
    assert "my_search=request.args.get('my_search', '')" in routes
    assert "my_status=request.args.get('my_status', '')" in routes
