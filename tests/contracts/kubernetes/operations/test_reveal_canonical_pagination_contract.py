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
    assert "table_registry.clear_filters_link(" in source
    assert "'kubernetes_operations.reveal_secret'," in source
    assert 'table_ui.table_classes(' in source
    assert 'table_ui.head_classes()' in source
    assert 'table_ui.body_classes()' in source
    assert 'table_ui.row_classes()' in source
    assert "table_ui.inventory_block_header(" in source
    assert "'my-secret-reveal-loading'," in source
    assert 'loading_bar.render(' not in source
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



def test_my_reveal_requests_use_approved_header_loading_filter_and_result_count() -> None:
    source = (ROOT / 'app/templates/kubernetes/operations/secrets/_reveal_request_status.html').read_text()
    table = (ROOT / 'app/templates/components/table.html').read_text()
    registry = (ROOT / 'app/templates/components/table_registry.html').read_text()

    assert 'components/table.html' in source
    assert 'components/table_primitives.html' not in source
    assert 'table_ui.inventory_block_header(' in source
    assert "result_count=my_reveal_pagination.total_items" in source
    assert 'components/loading_bar.html' not in source
    assert 'loading_bar.render(loading_id, label=loading_label)' in table
    assert 'table_registry.clear_filters_link(' in source
    assert "my_reveal_filters.search or my_reveal_filters.status or my_reveal_filters.sort != 'newest'" in source
    assert source.index('table_registry.clear_filters_link(') < source.index('table_ui.inventory_block_header(')
    assert source.index('table_ui.inventory_block_header(') < source.index('table_registry.filter_form(')
    assert source.count('table_registry.clear_filters_link(') == 1
    assert "macro clear_filters_link(" in registry

    assert "table_ui.table_classes('min-w-[920px]')" in source
    assert 'table_ui.title_cell(item.secret_name' in source
    assert 'table_ui.cell_classes(action=true)' in source
    assert 'table_ui.header_cell_classes(action=true)' in source
    assert 'aria-label="My Reveal Requests"' in source
    assert 'aria-label="Filter my protected reveal requests"' in source
    assert "page_param='my_page'" in source
    assert "per_page_param='my_per_page'" in source
    assert "table_registry.footer('kubernetes_operations.reveal_secret'" in source
    assert 'No Matching Reveal Requests' in source


def test_my_reveal_request_actions_preserve_approval_and_one_time_security() -> None:
    source = (ROOT / 'app/templates/kubernetes/operations/secrets/_reveal_request_status.html').read_text()
    actions = (ROOT / 'app/templates/components/action_button.html').read_text()
    shared_table = (ROOT / 'app/templates/components/table.html').read_text()

    assert 'step_up_active' in source
    assert "item.status == 'approved'" in source
    assert "item.status == 'expired'" in source
    assert "item.status == 'pending'" in source
    assert "item.status == 'revealed'" in source
    assert "item.status == 'denied'" in source
    assert "url_for('kubernetes_operations.reveal_secret_value', request_id=item.id)" in source
    assert "url_for('kubernetes_operations.reveal_secret', cluster_id=item.cluster_id" in source
    assert 'hx-post="{{ url_for(' in source
    assert 'hx-target="#reveal-value-output"' in source
    assert 'hx-disabled-elt="this"' in source
    assert 'name="csrf_token"' in source
    assert 'action_button.classes(\'primary\')' in source
    assert 'table_ui.action_classes()' in source
    assert 'macro classes(' in actions
    assert 'macro action_classes(' in shared_table
    assert 'href="#reveal-session-step-up"' in source
    assert 'Expires {{ item.expires_at|user_datetime }}' in source
    assert 'No action available' in source
    assert 'item.ticket_reference or' in source
    assert 'item.cluster.name ~' in source
