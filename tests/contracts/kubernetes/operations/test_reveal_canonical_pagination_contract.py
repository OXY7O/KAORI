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
    assert 'data-reveal-once-action' in source
    assert 'class="{{ table_ui.action_classes() }}"' in source
    assert 'table_ui.action_classes()' in source
    assert 'macro action_classes(' in shared_table
    assert 'data-reveal-step-up-trigger' in source
    assert "reveal_view='mine', _anchor='reveal-session-step-up'" in source
    assert 'Expires {{ item.expires_at|user_datetime }}' in source
    assert 'No action available' in source
    assert 'item.ticket_reference or' in source
    assert 'item.cluster.name ~' in source



def test_pending_approval_table_uses_full_canonical_registry_and_permission_scope() -> None:
    template = (ROOT / 'app/templates/kubernetes/operations/secrets/_reveal_pending_approvals.html').read_text()
    shared = (ROOT / 'app/templates/components/table.html').read_text()
    registry = (ROOT / 'app/templates/components/table_registry.html').read_text()
    service = (ROOT / 'app/kubernetes/operations/secrets/reveal_service.py').read_text()
    routes = (ROOT / 'app/kubernetes/operations/secrets/reveal_routes.py').read_text()

    assert 'table_ui.inventory_block_header(' in template
    assert "result_count=pending_reveal_pagination.total_items" in template
    assert "'pending-secret-reveal-loading'" in template
    assert "loading_bar.render(loading_id, label=loading_label)" in shared
    assert 'loading_bar.render(' not in template
    assert "table_registry.filter_form(" in template
    assert "table_registry.clear_filters_link(" in template
    assert 'pending_reveal_filters.search or pending_reveal_filters.sort != \'oldest\'' in template
    assert template.index("table_registry.clear_filters_link(") < template.index('table_ui.inventory_block_header(')
    assert template.index('table_ui.inventory_block_header(') < template.index('table_registry.filter_form(')
    assert 'table_ui.search_field(' in template
    assert "name=\"pending_sort\"" in template
    assert 'table_ui.title_cell(item.secret_name' in template
    assert 'table_ui.header_cell_classes(action=true)' in template
    assert 'table_ui.cell_classes(action=true)' in template
    assert 'table_ui.table_classes(' in template
    assert 'components/states/_empty_state.html' in template
    assert 'No Pending Approvals' in template
    assert "table_registry.footer(" in template
    assert "page_param='pending_page'" in template
    assert "per_page_param='pending_per_page'" in template
    assert 'my_page' in template and 'my_per_page' in template
    assert 'my_search' in template and 'my_status' in template and 'my_sort' in template
    assert "macro filter_form(" in registry
    assert "macro footer(" in registry

    # The filtered data remains permissioned by the backend, not client labels.
    assert "if can_approve:" in service
    assert "SecretRevealRequest.query.filter_by(status='pending')" in service
    assert "pending_search_value = str(pending_search or '').strip()[:120]" in service
    assert "pending_ordering = 'newest' if pending_sort == 'newest' else 'oldest'" in service
    assert "func.lower(SecretRevealRequest.secret_name).contains(pending_term, autoescape=True)" in service
    assert "func.lower(SecretRevealRequest.namespace).contains(pending_term, autoescape=True)" in service
    assert "func.lower(SecretRevealRequest.key_name).contains(pending_term, autoescape=True)" in service
    assert "func.lower(SecretRevealRequest.ticket_reference).contains(pending_term, autoescape=True)" in service
    assert "SecretRevealRequest.requested_at.asc(), SecretRevealRequest.id.asc()" in service
    assert "SecretRevealRequest.requested_at.desc(), SecretRevealRequest.id.desc()" in service
    assert "'pending_reveal_filters': {'search': pending_search_value, 'sort': pending_ordering}" in service
    assert "@permission_required('kubernetes_secrets.approve_reveal')" in routes
    assert "pending_search=request.args.get('pending_search', '')" in routes
    assert "pending_sort=request.args.get('pending_sort', 'oldest')" in routes


def test_pending_decision_editor_preserves_security_and_prevents_poll_loss() -> None:
    template = (ROOT / 'app/templates/kubernetes/operations/secrets/_reveal_pending_approvals.html').read_text()
    poller = (ROOT / 'app/static/js/secret_reveal_workspace.js').read_text()
    detail = (ROOT / 'app/static/js/detail_rows.js').read_text()
    routes = (ROOT / 'app/kubernetes/operations/secrets/reveal_routes.py').read_text()

    assert "item.requester_user_id == current_user.id" in template
    assert "item.requester_user_id != current_user.id" in template
    assert 'Another approver required' in template
    assert 'data-detail-toggle' in template
    assert 'data-detail-row="pending-approval-editor-{{ item.id }}"' in template
    assert 'data-detail-target="pending-approval-decision-{{ item.id }}"' in template
    assert 'data-detail-group="pending-reveal-approvals"' in template
    assert 'class="hidden bg-surface-hover"' in template
    assert 'data-detail-static="true"' in template
    assert 'data-approval-decision-editor' in template
    assert 'data-open="false"' in template
    assert 'aria-expanded="false"' in template
    assert 'closeGroup(button.dataset.detailGroup' in detail
    assert "row.classList.add('hidden')" in detail
    assert "row.classList.remove('hidden')" in detail
    assert "owner.querySelector?.('[data-approval-decision-editor][data-open=\"true\"]')" in poller
    assert "window.htmx.ajax('GET', url, { target, swap: 'outerHTML' })" in poller
    assert 'name="csrf_token"' in template
    assert 'name="decision_note"' in template
    assert 'maxlength="500"' in template
    assert 'name="decision"' in template
    assert 'value="deny"' in template and 'value="approve"' in template
    assert "table_ui.action_classes(destructive=true)" in template
    assert "table_ui.action_classes()" in template
    assert "action_button.classes('primary')" not in template
    assert "url_for('kubernetes_operations.decide_secret_reveal_request', request_id=item.id)" in template
    assert "def decide_secret_reveal_request(request_id: str)" in routes
    assert "_validate_secret_operation_csrf()" in routes
    assert "approver_user_id=current_user.id" in routes
    assert "if decision not in {'approve', 'deny'}:" in routes
    assert 'secret_value' not in template



def test_reveal_history_read_does_not_expire_globally_or_load_all_approvers() -> None:
    service = read('app/kubernetes/operations/secrets/reveal_service.py')
    model = read('app/models/secret_reveal.py')
    table = read('app/templates/kubernetes/operations/secrets/_reveal_request_status.html')
    assert '_expire_stale_requests()' not in service
    assert 'effective_status = case(' in service
    assert 'my_query = my_query.filter(effective_status == state_filter)' in service
    assert "SecretRevealRequest.expires_at > now" in service
    assert 'item.effective_status' in table
    assert 'linked_request.effective_status' in table
    assert 'def effective_status(self) -> str:' in model
    assert 'return \'expired\' if deadline <=' in model

    approvers = service.split('def get_secret_reveal_approvers(', 1)[1]
    approvers = approvers.split('\ndef rollback_secret_reveal_transaction(', 1)[0]
    assert 'Permission.key ==' in approvers
    assert 'Role.is_active.is_(True)' in approvers
    assert 'User.role_id.in_(authorized_roles)' in approvers
    assert 'User.account_is_active.is_(True)' in approvers
    assert 'User.deleted_at.is_(None)' in approvers
    assert "User.auth_source == 'database'" in approvers
    assert 'user.has_permission(' not in approvers
