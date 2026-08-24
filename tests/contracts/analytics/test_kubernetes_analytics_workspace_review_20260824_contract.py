from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


def test_requested_analytics_guidance_is_concise_without_losing_evidence_boundaries() -> None:
    forecast_snapshot = read('app/templates/kubernetes/analytics/overview/partials/_forecast_snapshot.html')
    utilization_trend = read('app/templates/kubernetes/analytics/utilization/partials/_trend.html')
    utilization_overview = read('app/templates/kubernetes/analytics/utilization/partials/_overview.html')
    capacity_risk = read('app/templates/kubernetes/analytics/capacity/partials/_risk.html')
    storage_overview = read('app/templates/kubernetes/analytics/storage/partials/_overview.html')
    tenant = read('app/templates/kubernetes/analytics/workload/partials/_tenant_quota_section.html')
    forecast = read('app/templates/kubernetes/analytics/forecast/partials/_forecast_section.html')

    for expected, source in (
        (
            'Validate signal quality, growth drivers, and the nearest threshold ETA before scheduling changes.',
            forecast_snapshot,
        ),
        (
            'Compare aligned trends across the selected window before changing capacity or workload placement.',
            utilization_trend,
        ),
        ('Unknown capacity stays Unknown; never treat it as zero utilization or Healthy.', utilization_overview),
        ('Lower headroom gets higher priority; unavailable evidence stays Unknown.', capacity_risk),
        ('Aggregate includes only nodes with paired capacity and available-byte evidence.', storage_overview),
        ('Usage includes only claims with paired capacity and used-byte evidence.', storage_overview),
        (
            'Review the tightest ResourceQuota, allocation, and active-Pod demand before tenant changes.',
            tenant,
        ),
        ('Latest daily average:', forecast),
        ("At ' ~ selected_forecast_horizon ~ ', projected demand reaches ", forecast),
        ('Historical averages are solid; projections are dashed against the capacity baseline.', forecast),
    ):
        assert expected in source

    for verbose in (
        'Validate historical signal quality, growth drivers, and the nearest threshold ETA before scheduling capacity or workload changes.',
        'Unknown capacity remains Unknown; it is never translated into zero utilization or a Healthy posture.',
        'Lower headroom receives higher operational priority.',
        'Latest committed daily average uses ',
        'Daily historical averages are solid; the selected model projection is dashed.',
    ):
        assert verbose not in '\n'.join(
            (forecast_snapshot, utilization_trend, utilization_overview, capacity_risk, storage_overview, tenant, forecast)
        )


def test_forecast_projection_summary_uses_scannable_list_and_canonical_typography() -> None:
    forecast = read('app/templates/kubernetes/analytics/forecast/partials/_forecast_section.html')

    assert 'aria-label="Projected capacity details"' in forecast
    assert '<span class="font-medium text-content-secondary">Peak:</span>' in forecast
    assert '<span class="font-medium text-content-secondary">Horizon endpoint:</span>' in forecast
    assert '<span class="font-medium text-content-secondary">Baseline:</span>' in forecast
    assert 'peak of {{ item.capacity_display }} · horizon endpoint' not in forecast
    assert 'text-3xl font-semibold tabular-nums' in forecast
    assert 'text-3xl font-bold' not in forecast


def test_record_detail_modal_widths_fit_dense_analytics_evidence() -> None:
    modal = read('app/templates/kubernetes/analytics/components/_record_detail_modal.html')
    alerts = read('app/templates/kubernetes/analytics/alerts/partials/_alerts_table_row.html')
    tenant = read('app/templates/kubernetes/analytics/workload/partials/_tenant_quota_section.html')
    mapping = read('app/templates/kubernetes/analytics/workload/partials/_workload_mapping_section.html')

    assert "size == 'expanded'" in modal
    assert 'max-w-7xl' in modal
    assert 'max-w-[112rem]' in modal
    assert "size='expanded'" in alerts
    assert "size='expanded'" in tenant
    assert "size='workspace'" in mapping
    assert mapping.count('minmax(18rem,1.25fr)') == 2
    assert 'sm:whitespace-nowrap' in mapping


def test_tenant_and_filesystem_record_loading_uses_full_width_stacked_header_contract() -> None:
    tenant = read('app/templates/kubernetes/analytics/workload/partials/_tenant_quota_section.html')
    filesystem = read('app/templates/kubernetes/analytics/storage/partials/_filesystem_panel.html')

    for title, indicator, source in (
        ('Tenant Quota Records', 'tenant-quota-loading-indicator', tenant),
        ('Node Filesystem Records', 'storage-filesystem-loading-indicator', filesystem),
    ):
        title_position = source.index(title)
        loader_position = source.index('loading_bar.render', title_position)
        header_end = source.index('</header>', title_position)
        assert title_position < loader_position < header_end
        assert 'border-b border-outline-subtle px-5 py-4 sm:px-6' in source
        assert 'flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between' in source
        assert indicator in source


def test_notification_deck_is_wider_and_active_work_context_is_sectioned() -> None:
    deck = read('app/templates/components/navigation/_notification_center.html')
    items = read('app/templates/platform_operations/notifications/components/_activity_center_items.html')
    progress = read('app/templates/components/progress_bar.html')

    assert 'max-w-lg' in deck
    assert 'max-w-md flex-col' not in deck
    assert '<dt class="w-12 shrink-0 font-medium text-content-secondary">Source</dt>' in items
    assert '<dt class="w-12 shrink-0 font-medium text-content-secondary">Scope</dt>' in items
    assert "job.progress_target.split(' · ')" in progress
    assert 'aria-label="Current work context"' in progress
    assert '<p class="font-medium text-content-secondary">Current</p>' in progress
    assert 'Current:</span> {{ job.progress_target }}' in progress  # retained for non-compact surfaces


def test_kubernetes_analytics_templates_keep_tokenized_visual_language() -> None:
    analytics_root = ROOT / 'app/templates/kubernetes/analytics'
    content = '\n'.join(path.read_text(encoding='utf-8') for path in analytics_root.rglob('*.html'))

    forbidden = (
        'text-[',
        'tracking-[',
        'rounded-[',
        '#7C3AED',
        'bg-violet-',
        'text-violet-',
        'bg-gray-',
        'text-gray-',
    )
    for token in forbidden:
        assert token not in content
