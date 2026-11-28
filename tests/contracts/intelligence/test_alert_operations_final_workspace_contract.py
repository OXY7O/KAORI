from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_active_queue_owns_loading_filter_actions_and_modal_review() -> None:
    active = read('app/templates/intelligence/partials/_alert_ops_active.html')
    table = read('app/templates/intelligence/partials/_alert_ops_active_table.html')
    page = read('app/templates/intelligence/alert_intelligence.html')

    assert 'Active Alert Queue' in active
    assert "loading_bar.render('alert-operations-active-loading'" in active
    active_header = active.split('id="alert-operations-active-registry"', 1)[1].split('</header>', 1)[0]
    assert "loading_bar.render('alert-operations-active-loading'" in active_header
    assert active.index("loading_bar.render('alert-operations-active-loading'") < active.index(
        'id="alert-operations-filter-form"'
    )
    assert "table_label.result_count(payload.active_pagination.total_items)" in active
    assert 'Clear Filters' in active
    assert 'data-resource-detail-toggle' in table
    assert 'data-alert-case-expanded-row=' not in table
    assert "resource_detail_modal.host('Alert Operations'" in page
    assert (
        "record_pagination.render(payload.active_pagination, 'page', 'per_page', 'alert-operations-active-registry'"
        in table
    )


def test_alert_case_asset_namespace_metadata_has_no_vertical_divider() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_ops_case_workspace.html')

    asset_namespace = workspace.split(
        "{% for icon, label, value in [('boxes', 'Asset', case.asset_name), ('layers-3', 'Namespace', case.namespace)] %}",
        1,
    )[1].split('{% endfor %}', 1)[0]
    assert 'border-r' not in asset_namespace


def test_routing_workspace_is_table_led_and_crud_uses_modal() -> None:
    routing = read('app/templates/intelligence/partials/_alert_ops_routing.html')
    editor = read('app/templates/intelligence/partials/_alert_ops_routing_editor_modal.html')
    routes = read('app/intelligence/alert_intelligence/routes.py')
    application = read('app/intelligence/alert_intelligence/application.py')

    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    assert 'Routing Guidance' not in routing
    assert "payload.tab == 'routing' and not payload.provider_case_mode" in workspace
    assert 'Routing Guidance: keep policy scope narrow' in workspace
    assert 'Policy Registry' in routing
    assert "table_ui.table_classes('w-full table-fixed')" in routing
    assert 'overflow-x-auto' not in routing
    assert 'Policy Details' in routing
    assert 'data-resource-detail-toggle' in routing
    assert 'alert_intelligence.routing_policy_details' in routing
    assert 'max-h-[30rem]' not in routing
    assert 'data-alert-channel-readiness-summary' in routing
    assert 'data-dialog-target="alert-channel-readiness-dialog"' in routing
    assert 'Channel Readiness' in routing
    assert 'Use Channel Defaults or Create a Governed Policy' in routing
    assert routing.index('Channel Readiness') < routing.index('Policy Registry')
    assert routing.count('class="{{ table_ui.action_classes(size=\'header\') }}"') >= 2
    assert 'data-kaori-detail-variant="modal"' in editor
    assert 'Identity & Cadence' in editor
    assert 'Match Scope & Channels' in editor
    assert 'bg-kaori-soft text-kaori-primary' in editor
    assert 'Matcher tip:' not in editor
    assert 'How to match' in editor
    assert 'Policy Checklist' in editor
    assert '{% import "components/action_button.html" as action_button %}' in editor
    assert "action_button.classes('critical')" in editor
    assert "action_button.classes('primary')" in editor
    assert 'Delete Policy' in editor
    assert 'def routing_policy_details(policy_ref: str)' in routes
    assert 'def delete_routing_policy(policy_id: int)' in routes
    assert 'def delete_routing_policy_command' in application


def test_silence_registry_has_full_kaori_filter_loading_and_pagination_contract() -> None:
    template = read('app/templates/intelligence/partials/_alert_ops_silences.html')
    service = read('app/intelligence/alert_intelligence/service.py')

    assert "loading_bar.render('alert-operations-silence-loading'" in template
    silence_header = template.split('id="alert-operations-silence-registry"', 1)[1].split('</header>', 1)[0]
    assert "loading_bar.render('alert-operations-silence-loading'" in silence_header
    assert 'table_registry.filter_form' in template
    assert 'silence_q' in template
    assert 'silence_severity' in template
    assert 'Clear Filters' not in template  # canonical clear action macro owns the label
    assert 'table_registry.clear_filters_action' in template
    assert 'table_registry.footer' in template
    assert "'silence_filters': {'q': silence_search, 'severity': silence_severity}" in service
    assert 'def _active_silence_rows(' in service
    assert "if severity != 'all':" in service


def test_resolved_workspace_adds_posture_and_keeps_clear_next_to_archive_policy() -> None:
    template = read('app/templates/intelligence/partials/_alert_ops_history.html')
    service = read('app/intelligence/alert_intelligence/service.py')

    assert 'Resolved Alert Posture' in template
    assert 'Evidence Retention' in template
    assert 'Archive Policy' in template
    assert 'table_registry.clear_filters_action' in template
    assert "loading_bar.render('alert-operations-history-loading'" in template
    assert "'resolved_total': len(history_cases)" in service
    assert 'def _case_counts_from_query(query) -> dict[str, int]:' in service
    assert "and_(historical, AlertCase.workflow_state == 'closed')" in service
    assert "and_(historical, AlertCase.closure_reason == 'false_positive')" in service
    assert 'paginate_query(' in service
    assert 'data-resource-detail-toggle' in template
    assert 'alert_intelligence.case_details' in template
    assert 'Close Review' not in template


def test_notification_templates_have_posture_and_guidance_before_registry() -> None:
    template = read('app/templates/intelligence/partials/_alert_ops_templates.html')

    assert 'Notification Templates' in template
    assert 'Template Guidance' in template
    assert 'Eligible Channels' in template
    assert 'Template Registry' in template
    assert '<details class="group bg-surface-card">' in template
    assert 'Rendered Preview' in template
    assert 'Save Override' in template


def test_context_loading_is_isolated_from_tab_and_registry_loading() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_scope_form.html')

    context_form = workspace.split('id="alert-intelligence-context-form"', 1)[1].split('</form>', 1)[0]
    assert 'hx-indicator="#alert-intelligence-context-loading"' in context_form
    assert 'hx-indicator="#alert-intelligence-loading"' not in context_form
    assert "loading_bar.render('alert-intelligence-context-loading'" in workspace
    assert "indicator_id='alert-intelligence-loading'" not in workspace
    assert "hx_indicator='#alert-intelligence-loading'" not in workspace
    assert 'hx-trigger="submit"' in context_form


def test_resolved_case_review_uses_dedicated_modal_content_and_modal_refresh_contract() -> None:
    history = read('app/templates/intelligence/partials/_alert_ops_history.html')
    modal = read('app/templates/intelligence/partials/_alert_ops_resolved_case_modal.html')
    routes = read('app/intelligence/alert_intelligence/routes.py')
    route_utils = read('app/intelligence/alert_intelligence/route_utils.py')

    assert 'data-resource-detail-toggle' in history
    assert "tab='resolved'" in history
    activity = read('app/templates/intelligence/partials/_alert_ops_case_activity_streams.html')
    assert 'data-kaori-detail-variant="modal"' in modal
    for required in ('Verification & Closure', 'Verification Pending', 'Resolution Evidence', 'Postmortem & Learning'):
        assert required in modal
    assert 'Resolution Summary' in modal
    assert 'Recovery Steps & References' in modal
    assert 'xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]' in modal
    assert 'rounded-xl border border-outline-subtle bg-surface-card' in modal
    for required in ('Incident Timeline', 'Notification Delivery Ledger'):
        assert required in activity
    assert 'modal_case_response as _modal_case_response' in routes
    assert "if payload.get('tab') == 'resolved'" in route_utils
    assert "requested_tab = str(tab or request.form.get('tab') or 'active')" in route_utils
    assert "if payload.get('selected_case') is None:" in route_utils


def test_case_modal_uses_persistent_summary_host_and_shared_activity_streams() -> None:
    active = read('app/templates/intelligence/partials/_alert_ops_case_workspace.html')
    resolved = read('app/templates/intelligence/partials/_alert_ops_resolved_case_modal.html')
    routing = read('app/templates/intelligence/partials/_alert_ops_routing_editor_modal.html')
    recommendation = read('app/templates/intelligence/partials/_recommendation_detail_content.html')
    modal_host = read('app/templates/components/resource_detail_modal.html')
    activity = read('app/templates/intelligence/partials/_alert_ops_case_activity_streams.html')

    assert 'id="resource-detail-modal-summary"' in modal_host
    assert 'data-resource-detail-summary-host' in modal_host
    assert 'data-resource-detail-summary' in recommendation
    for template in (active, resolved, routing):
        assert 'data-resource-detail-summary' in template
    for template in (active, resolved):
        assert 'hx-swap-oob="innerHTML:#resource-detail-modal-summary"' in template
        assert 'sticky top-0 z-20' not in template
    assert '_alert_ops_case_activity_streams.html' in active
    assert '_alert_ops_case_activity_streams.html' in resolved
    assert 'Incident Timeline' in activity
    assert 'Notification Delivery Ledger' in activity
    assert 'Earlier Timeline Events' in activity
    assert 'Earlier Delivery Attempts' in activity
    assert 'max-h-72' in activity


def test_routing_registry_has_canonical_filters() -> None:
    routing = read('app/templates/intelligence/partials/_alert_ops_routing.html')
    service = read('app/intelligence/alert_intelligence/service.py')

    assert 'table_registry.filter_form' in routing
    assert 'routing_q' in routing
    assert 'routing_domain' in routing
    assert 'routing_status' in routing
    assert 'table_registry.clear_filters_action' in routing
    assert "'routing_filters': {'q': routing_search, 'domain': routing_domain, 'status': routing_status}" in service
    assert 'def _filter_routing_policies(' in service


def test_modal_case_mutations_refresh_visible_registry_via_htmx_event() -> None:
    routes = read('app/intelligence/alert_intelligence/routes.py')
    route_utils = read('app/intelligence/alert_intelligence/route_utils.py')
    active = read('app/templates/intelligence/partials/_alert_ops_active.html')
    silences = read('app/templates/intelligence/partials/_alert_ops_silences.html')
    resolved = read('app/templates/intelligence/partials/_alert_ops_history.html')

    assert 'modal_case_response as _modal_case_response' in routes
    assert "response.headers['HX-Trigger'] = 'alertCaseChanged'" in route_utils
    assert 'hx-trigger="alertCaseChanged from:body"' in active
    assert 'hx-trigger="alertCaseChanged from:body"' in silences
    assert 'hx-trigger="alertCaseChanged from:body"' in resolved


def test_context_filter_owns_only_context_loading_lifecycle() -> None:
    workspace = read('app/templates/intelligence/partials/_alert_scope_form.html')
    context_form = workspace.split('id="alert-intelligence-context-form"', 1)[1].split('</form>', 1)[0]

    assert 'hx-indicator="#alert-intelligence-context-loading"' in context_form
    assert 'hx-sync="this:replace"' in context_form
    assert 'hx-disabled-elt="#alert-intelligence-context-form fieldset"' in context_form
    assert 'hx-select="#alert-intelligence-page-content"' in context_form
    assert '#alert-operations-active-loading' not in context_form
    assert '#alert-operations-silence-loading' not in context_form
    assert "indicator_id='alert-intelligence-loading'" not in workspace
    assert "hx_indicator='#alert-intelligence-loading'" not in workspace


def test_active_queue_filter_does_not_listen_to_operational_context_selects() -> None:
    active = read('app/templates/intelligence/partials/_alert_ops_active.html')
    active_form = active.split('id="alert-operations-filter-form"', 1)[1].split('</form>', 1)[0]

    assert 'hx-trigger="change, input changed delay:350ms"' in active_form
    assert 'from:select' not in active_form
    assert 'from:input' not in active_form
    assert 'hx-indicator="#alert-operations-active-loading"' in active_form


def test_alert_intelligence_section_headers_use_canonical_text_hierarchy() -> None:
    templates = (
        'app/templates/intelligence/partials/_alert_ops_overview.html',
        'app/templates/intelligence/partials/_alert_ops_active.html',
        'app/templates/intelligence/partials/_alert_ops_routing.html',
        'app/templates/intelligence/partials/_alert_ops_templates.html',
        'app/templates/intelligence/partials/_alert_ops_history.html',
    )
    for relative in templates:
        template = read(relative)
        assert 'table_ui.block_title_classes()' in template, relative
        assert 'table_ui.block_description_classes()' in template, relative

    table_primitives = read('app/templates/components/table_primitives.html')
    assert 'text-base font-semibold text-content-primary' in table_primitives
    assert 'mt-1 text-sm leading-6 text-content-secondary' in table_primitives

    overview = read('app/templates/intelligence/partials/_alert_ops_overview.html')
    for title in ('Alert Operations Snapshot', 'Lifecycle Control', 'Operational Readiness'):
        assert f'<h3 class="{{{{ table_ui.block_title_classes() }}}}">{title}</h3>' in overview

    routing = read('app/templates/intelligence/partials/_alert_ops_routing.html')
    for title in ('Routing & Channels', 'Channel Readiness', 'Policy Registry'):
        assert f'<h3 class="{{{{ table_ui.block_title_classes() }}}}">{title}</h3>' in routing

    templates_source = read('app/templates/intelligence/partials/_alert_ops_templates.html')
    for title in ('Notification Templates', 'Template Registry'):
        assert f'<h3 class="{{{{ table_ui.block_title_classes() }}}}">{title}</h3>' in templates_source


def test_alert_intelligence_modals_follow_recommendation_review_visual_language() -> None:
    active = read('app/templates/intelligence/partials/_alert_ops_case_workspace.html')
    resolved = read('app/templates/intelligence/partials/_alert_ops_resolved_case_modal.html')
    routing = read('app/templates/intelligence/partials/_alert_ops_routing_editor_modal.html')

    for template in (active, resolved):
        assert 'data-kaori-alert-review-layout="recommendation-inspired"' in template
        assert 'data-kaori-detail-shell' in template
        assert 'border border-brand-outline bg-kaori-soft text-kaori-primary' in template
        assert 'Committed Evidence' in template
        assert 'data-kaori-alert-status-rail' in template
        assert 'data-resource-detail-summary' in template
    assert 'Alert Case Review' in active
    assert 'Resolved Case Review' in resolved
    assert 'data-kaori-routing-modal-layout="recommendation-inspired"' in routing
    assert 'data-kaori-detail-shell' in routing
    assert 'Governed Delivery' in routing


def test_active_alert_table_names_eight_columns_and_preserves_source_state() -> None:
    from jinja2 import Environment

    source = read('app/templates/intelligence/partials/_alert_ops_active_table.html')
    Environment().parse(source)
    assert source.count('<table ') == 1
    assert source.count('<caption class="sr-only">') == 1
    assert 'Active alert cases and operational review actions' in source
    assert source.count('scope="col"') == 8
    assert "table_ui.table_classes('min-w-[1080px]')" in source
    assert 'record_pagination.render(' in source
    assert 'resource-detail-modal' in source
    assert "'source_state': payload.filters.source_state" in source
    for heading in ('Alert', 'Severity', 'Source', 'Workflow', 'Owner', 'Age', 'Delivery', 'Action'):
        assert f'>{heading}</th>' in source


def test_alert_lifecycle_navigation_is_above_hero_and_scope_preserving() -> None:
    page = read('app/templates/intelligence/partials/_alert_intelligence_page.html')
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    summary = read('app/templates/intelligence/partials/_alert_intelligence_summary.html')

    assert page.count('workspace_tabs.render_navigation(') == 1
    assert page.index('workspace_tabs.render_navigation(') < page.index('page_hero.shell_classes()')
    assert "hx_target='#alert-intelligence-page-content'" in page
    assert 'hx-sync="#alert-intelligence-page-content:replace"' in page
    assert "'domain': payload.domain, 'asset': payload.selected_asset_key" in page
    for tab in ('overview', 'active', 'routing', 'templates', 'silences', 'resolved'):
        assert f"tab='{tab}', **tab_query" in page
    assert 'content_tabs.render_links' not in workspace
    context = read('app/templates/intelligence/partials/_alert_scope_form.html')
    assert 'name="tab"' in context
    assert 'value="{{ scope.tab }}"' in context
    assert 'id="alert-intelligence-context-form"' not in workspace
    assert 'lifecycle navigation above' in summary


def test_lifecycle_control_balances_readiness_height_without_empty_card_space() -> None:
    from jinja2 import Environment

    overview = read('app/templates/intelligence/partials/_alert_ops_overview.html')
    Environment().parse(overview)
    lifecycle = overview.split('>Lifecycle Control</h3>', 1)[1].split('</section>', 1)[0]
    assert 'grid items-stretch gap-4 xl:grid-cols-' in overview
    assert 'flex min-w-0 flex-col overflow-hidden' in overview
    assert 'data-alert-lifecycle-metrics' in lifecycle
    assert 'grid flex-1 auto-rows-fr grid-cols-1 gap-px bg-outline-subtle sm:grid-cols-2' in lifecycle
    assert 'xl:grid-cols-4' not in lifecycle
    assert 'flex min-w-0 flex-col justify-center bg-surface-card' in lifecycle
    for field in ('acknowledged', 'silenced', 'resolved_today', 'routing_policies'):
        assert lifecycle.count(f'payload.summary.{field}') >= 1
    assert 'readiness_ui.readiness_actions()' in overview


def test_each_alert_tab_uses_shared_section_intro_between_summary_and_workspace() -> None:
    from jinja2 import Environment

    page = read('app/templates/intelligence/partials/_alert_intelligence_page.html')
    Environment().parse(page)
    assert 'import "components/section_intro.html" as section_intro' in page
    assert page.count('section_intro.render(') == 1
    assert "section_intros.get(payload.tab, section_intros['overview'])" in page
    assert page.index('_alert_intelligence_summary.html') < page.index('section_intro.render(')
    assert page.index('section_intro.render(') < page.index('_alert_intelligence_workspace.html')
    assert 'data-alert-intelligence-tab-section="{{ payload.tab }}"' in page
    for tab, title in (
        ('overview', 'Alert Overview'),
        ('active', 'Active Alert Review'),
        ('routing', 'Routing & Channels'),
        ('templates', 'Notification Templates'),
        ('silences', 'Delivery Silences'),
        ('resolved', 'Recovery & Closure'),
    ):
        assert f"'{tab}': ('{title}', '" in page


def test_active_alert_triage_and_filters_follow_registry_hierarchy() -> None:
    from jinja2 import Environment

    active = read('app/templates/intelligence/partials/_alert_ops_active.html')
    table = read('app/templates/intelligence/partials/_alert_ops_active_table.html')
    workspace = read('app/templates/intelligence/partials/_alert_intelligence_workspace.html')
    for source in (active, table, workspace):
        Environment().parse(source)
    assert 'data-alert-triage-metrics' in active
    assert 'Triage Guidance' not in active
    assert 'Triage: prioritize critical or source-unknown cases' in workspace
    assert 'data-alert-quick-views' not in active
    assert 'Quick Views' not in active
    assert 'quick_context' not in active
    assert active.index('id="alert-operations-active-registry"') < active.index('id="alert-operations-filter-form"')
    for field in ('q', 'severity', 'source_state', 'workflow'):
        assert f'name="{field}"' in active or f"search_field('{field}'" in active
    assert 'hx-sync="#alert-operations-active-registry:replace"' in active
    assert "table_ui.inventory_filter_bar_classes()" in active
    identity = table.split('data-alert-case-identity', 1)[1].split('</td>', 1)[0]
    assert identity.count('class="truncate ') == 3
    assert 'title="{{ case.alert_name }}"' in identity
    assert 'title="Case ID · {{ case.public_id }}"' in identity
    assert 'w-[38%] max-w-0' in table
    assert 'Case ID' in identity
    for field in ('alert_name', 'asset_name', 'namespace', 'public_id'):
        assert f'case.{field}' in identity
    assert 'case.source_type_label' not in identity
    assert 'case.source_type_label' in table


def test_case_evidence_facts_and_activity_streams_use_content_aware_layout() -> None:
    from jinja2 import Environment

    active = read('app/templates/intelligence/partials/_alert_ops_case_workspace.html')
    streams = read('app/templates/intelligence/partials/_alert_ops_case_activity_streams.html')
    for template in (active, streams):
        Environment().parse(template)
    assert 'data-alert-evidence-facts' in active
    assert 'fact_count = case.evidence_facts|length' in active
    assert "'sm:grid-cols-2' if fact_count > 1 else ''" in active
    assert "'xl:grid-cols-3' if fact_count == 3" in active
    assert "'sm:col-span-2 xl:col-span-1' if fact_count == 3 and loop.last" in active
    assert 'data-alert-evidence-streams' in streams
    assert 'flex min-w-0 flex-col overflow-hidden border' in streams
    assert 'group border-t' in streams
    assert 'data-alert-history-placement="independent"' in streams
    assert streams.count('timeline_row(event)') == 3
    assert streams.count('delivery_row(delivery)') == 3
    assert streams.count("sort(reverse=true, attribute='created_at')") == 2
    assert "case.deliveries|length ~ ' Records'" in streams
    assert "case.deliveries[0].attempt_count ~ ' Attempts'" in streams
    assert 'truncate' not in streams.replace('timeline_truncated', '')
    assert 'max-h-72' in streams


def test_activity_streams_share_intrinsic_rows_only_when_recent_counts_match() -> None:
    from datetime import UTC, datetime
    from html.parser import HTMLParser

    from jinja2 import Environment, FileSystemLoader

    class HistoryPlacementParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.articles = []
            self.history = {}

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if tag == 'article':
                self.articles.append(attributes.get('data-alert-evidence-panel'))
            if 'data-alert-evidence-history' in attributes:
                self.history[attributes['data-alert-evidence-history']] = tuple(
                    kind for kind in self.articles if kind is not None
                )

        def handle_endtag(self, tag):
            if tag == 'article':
                self.articles.pop()

    def history_parents(html):
        parser = HistoryPlacementParser()
        parser.feed(html)
        return parser.history

    env = Environment(loader=FileSystemLoader(ROOT / 'app/templates'), autoescape=True)
    env.filters['user_datetime'] = lambda value: value.isoformat()
    template = env.get_template('intelligence/partials/_alert_ops_case_activity_streams.html')
    timestamp = datetime(2026, 11, 28, tzinfo=UTC)
    event = {
        'icon': 'activity', 'tone': 'info', 'label': 'Firing Notified',
        'actor': 'KAORI Worker', 'summary': 'Event details', 'created_at': timestamp,
    }
    delivery = {
        'channel': 'KAORI Telegram', 'status': 'sent', 'event_label': 'Firing',
        'provider': 'Telegram', 'attempt_count': 1, 'created_at': timestamp,
        'sent_at': timestamp,
    }
    for count in range(1, 6):
        case = {
            'timeline_recent': [event] * count, 'timeline': [event] * count,
            'timeline_older': [event], 'deliveries_recent': [delivery] * count,
            'deliveries': [delivery] * count, 'deliveries_older': [delivery],
        }
        html = template.render(case=case)
        assert 'data-alert-evidence-aligned="true"' in html
        assert html.count('xl:grid-rows-subgrid') == 4
        assert html.count(f'xl:row-span-{count + 1}') == 2
        assert html.count(f'xl:row-span-{count}"') == 2
        assert html.count('data-alert-evidence-row') == count * 2 + 2
        assert html.count('min-h-6 min-w-0 flex-wrap items-center') == count * 2 + 2
        assert html.count('data-alert-history-placement="independent"') == 2
        assert history_parents(html) == {'timeline': (), 'delivery': ()}
        assert html.count(f'xl:row-start-{count + 2}') == 2
        assert 'xl:auto-rows-max xl:content-start' in html
        assert html.count('xl:col-start-1 xl:row-start-2') == 2
        assert html.count('self-start overflow-hidden rounded-b-xl') == 2
        assert html.index('data-alert-evidence-panel="timeline"') < html.index('data-alert-evidence-history="timeline"')
        assert html.index('data-alert-evidence-history="timeline"') < html.index('data-alert-evidence-panel="delivery"')

        case['deliveries_recent'] = [delivery] * (count - 1)
        html = template.render(case=case)
        assert 'data-alert-evidence-aligned="false"' in html
        assert 'xl:grid-rows-subgrid' not in html
        assert html.count('data-alert-evidence-row') == count * 2 + 1
        assert html.count('data-alert-history-placement="inline"') == 2
        assert history_parents(html) == {'timeline': ('timeline',), 'delivery': ('delivery',)}
        assert 'data-alert-history-placement="independent"' not in html

    case['deliveries_recent'] = [delivery] * count
    case['deliveries_older'] = []
    html = template.render(case=case)
    assert 'data-alert-evidence-aligned="true"' in html
    assert history_parents(html) == {'timeline': ()}
    assert 'data-alert-evidence-history="delivery"' not in html

    case['deliveries_older'] = [delivery]
    case['provider_delivery_qualified'] = False
    case['provider_delivery_state'] = 'no_claim'
    html = template.render(case=case)
    assert 'data-alert-evidence-aligned="false"' in html
    assert 'No Claim Recorded' in html
    assert html.count('data-alert-evidence-row') == count + 1
    assert 'data-alert-evidence-history="delivery"' not in html
    assert 'data-alert-history-placement="independent"' not in html


def test_alert_registry_header_labels_follow_canonical_order() -> None:
    registries = (
        ('_alert_ops_active.html', 'Active Alert Queue', 'payload.active_pagination.total_items'),
        ('_alert_ops_routing.html', 'Policy Registry', 'payload.routing_pagination.total_items'),
        ('_alert_ops_silences.html', 'Active Delivery Silences', 'payload.silence_pagination.total_items'),
        ('_alert_ops_history.html', 'Resolved Alerts', 'payload.history_pagination.total_items'),
        ('_alert_provider_history.html', 'Committed Provider Recovery & Closure', 'payload.active_pagination.total_items'),
        ('_vault_provider_routing.html', 'Scoped Firing Policies', 'routing.pagination.total_items'),
        ('_alert_channel_readiness_registry.html', 'Notification Channels', 'readiness.pagination.total_items'),
        ('_alert_ops_templates.html', 'Template Registry', 'payload.templates|length'),
    )
    for filename, title, count in registries:
        source = read(f'app/templates/intelligence/partials/{filename}')
        heading = f'<h3 class="{{{{ table_ui.block_title_classes() }}}}">{title}</h3>'
        start = source.index(heading)
        title_row = source[start:source.index('</div>', start)]
        result = f'table_label.result_count({count})'
        assert title_row.count(result) == 1
        assert title_row.count("variant='guide'") == 1
        assert title_row.index(result) < title_row.index('info_tip.render(')
        assert source.count(result) == 1


def test_routing_editor_compact_summary_and_bounded_channel_choices() -> None:
    from jinja2 import Environment

    editor = read('app/templates/intelligence/partials/_alert_ops_routing_editor_modal.html')
    Environment().parse(editor)
    rail = editor.split('data-kaori-routing-status-rail', 1)[1].split('</dl>', 1)[0]
    assert 'Editor Context' in rail and 'Channel Candidates' in rail
    assert 'available.count' in rail
    assert 'Based on initial policy scope' in rail
    assert 'Routing lifecycle' not in rail and 'Durable Alert Cases' not in rail
    assert 'max-h-64 divide-y divide-outline-subtle overflow-y-auto' in editor
    assert 'data-routing-channel-options' in editor
    assert 'name="channel_ids"' in editor
    assert 'if not channel_available' in editor
    assert 'channel.registry_eligible' in editor
    assert 'aria-describedby="routing-matcher-help"' in editor
    assert 'name="matchers" rows="3"' in editor
    assert 'data-routing-matchers' in editor
    assert '<details class="group border-t' in editor
    assert 'Policy Checklist' in editor
