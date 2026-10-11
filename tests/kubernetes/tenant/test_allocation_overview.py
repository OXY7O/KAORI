from __future__ import annotations

from types import SimpleNamespace

from jinja2 import Environment

from app.kubernetes.tenant.allocation_overview import (
    _partition_tenant_contributions,
    build_tenant_allocation_bars,
    describe_tightest_headroom,
    filter_tenant_contribution_rows,
    summarize_tenant_contributions,
)


def _summary(*, cpu_budget: str | None = "10", cpu_used: str | None = "6") -> dict:
    return {
        "budget": {
            "available": {
                "cpu": cpu_budget,
                "memory_bytes": str(20 * 1024**3),
                "pods": "100",
                "storage_bytes": None,
            }
        },
        "committed": {
            "cpu": cpu_used,
            "memory_bytes": str(8 * 1024**3),
            "pods": "24",
            "storage_bytes": str(10 * 1024**3),
        },
        "display": {
            "budget": {"cpu": "10.00 cores", "memory": "20.00 GiB", "pods": "100 pods", "storage": "Not Governed"},
            "committed": {"cpu": "6.00 cores", "memory": "8.00 GiB", "pods": "24 pods", "storage": "10.00 GiB"},
            "headroom": {"cpu": "4.00 cores", "memory": "12.00 GiB", "pods": "76 pods", "storage": "Not Governed"},
        },
    }


def _namespace(tenant_id: str, name: str, *, cpu: str = "1") -> SimpleNamespace:
    return SimpleNamespace(
        namespace=name,
        environment=SimpleNamespace(tenant_id=tenant_id, environment="development"),
        allocation_quota_json={
            "requests.cpu": cpu,
            "requests.memory": "1Gi",
            "pods": "5",
            "requests.storage": "2Gi",
        },
        provisioning_status="ready",
    )


def test_budget_composition_uses_committed_governance_values_not_utilization() -> None:
    bars = build_tenant_allocation_bars(_summary())
    assert [bar["key"] for bar in bars] == ["cpu", "memory_bytes", "pods", "storage_bytes"]
    assert bars[0]["known"] is True
    assert bars[0]["percent"] == "60.0"
    assert bars[0]["free_percent"] == "40.0"
    assert bars[1]["percent"] == "40.0"
    assert bars[2]["percent"] == "24.0"
    assert bars[3]["known"] is False
    assert bars[3]["state"] == "Not Governed"


def test_unknown_and_overcommitted_budget_does_not_claim_free_capacity() -> None:
    unknown = build_tenant_allocation_bars(_summary(cpu_budget=None))[0]
    assert unknown["known"] is False
    assert unknown["state"] == "Unknown"

    over = build_tenant_allocation_bars(_summary(cpu_budget="5", cpu_used="6"))[0]
    assert over["known"] is True
    assert over["percent"] == "100.0"
    assert over["free_percent"] == "0.0"
    assert over["state"] == "Overcommitted"
    assert over["shortfall"] == "1.00 cores"

    zero = build_tenant_allocation_bars(_summary(cpu_budget="0", cpu_used="0"))[0]
    assert zero["known"] is False
    assert zero["state"] == "Exhausted"


def test_budget_detail_percentages_remain_presentation_only_and_bound_unknown_states() -> None:
    normal = build_tenant_allocation_bars(_summary())
    assert [(bar["label"], bar["percent"], bar["free_percent"]) for bar in normal[:3]] == [
        ("CPU Requests", "60.0", "40.0"),
        ("Memory Requests", "40.0", "60.0"),
        ("Pod Slots", "24.0", "76.0"),
    ]
    assert normal[3]["known"] is False
    assert normal[3]["state"] == "Not Governed"

    overcommitted = build_tenant_allocation_bars(_summary(cpu_budget="5", cpu_used="6"))[0]
    assert overcommitted["state"] == "Overcommitted"
    assert overcommitted["percent"] == "100.0"
    assert overcommitted["free_percent"] == "0.0"
    assert overcommitted["shortfall"] == "1.00 cores"

    unknown = build_tenant_allocation_bars(_summary(cpu_budget=None))[0]
    assert unknown["known"] is False
    assert unknown["state"] == "Unknown"

    exhausted = build_tenant_allocation_bars(_summary(cpu_budget="0", cpu_used="0"))[0]
    assert exhausted["known"] is False
    assert exhausted["state"] == "Exhausted"


def test_created_and_adopted_tenants_share_one_canonical_ledger() -> None:
    created = SimpleNamespace(id="created", name="Created", provider_key="native_kubernetes", ownership_status="managed")
    adopted = SimpleNamespace(id="adopted", name="Adopted", provider_key="native_kubernetes", ownership_status="adopted")
    rows = _partition_tenant_contributions(
        [created, adopted],
        [_namespace("created", "created-ns", cpu="2"), _namespace("adopted", "adopted-ns", cpu="3")],
        {},
        [],
    )
    assert len(rows) == 2
    assert [r["allocation"]["cpu"] for r in rows] == ["2.00 cores", "3.00 cores"]
    assert [r["namespace_count"] for r in rows] == [1, 1]
    assert all(r["source"] == "Namespace Quotas" for r in rows)


def test_capsule_shared_tenant_quota_is_counted_once_not_per_namespace() -> None:
    capsule = SimpleNamespace(id="capsule", name="Capsule", provider_key="capsule", ownership_status="managed")
    rows = _partition_tenant_contributions(
        [capsule],
        [_namespace("capsule", "one"), _namespace("capsule", "two")],
        {"capsule": {"requests.cpu": "4", "requests.memory": "8Gi", "pods": "20", "requests.storage": "10Gi"}},
        [],
    )
    assert len(rows) == 1
    assert rows[0]["allocation"]["cpu"] == "4.00 cores"
    assert rows[0]["namespace_count"] == 2
    assert rows[0]["source"] == "Shared Tenant Quota"


def test_ambiguous_shared_quota_stays_unknown() -> None:
    capsule = SimpleNamespace(id="ambiguous", name="Ambiguous", provider_key="capsule", ownership_status="managed")
    rows = _partition_tenant_contributions([capsule], [_namespace("ambiguous", "one")], {}, ["ambiguous"])
    assert rows[0]["unknown"] is True
    assert rows[0]["source"] == "Ambiguous Shared Quota"
    assert rows[0]["allocation"]["cpu"] == "N/A"


def test_near_capacity_exposes_tightest_governed_dimension_without_reclassifying() -> None:
    bars = build_tenant_allocation_bars(_summary())
    assert describe_tightest_headroom(bars, "Near Capacity") == "Lowest headroom: CPU Requests (40.0%)"
    assert describe_tightest_headroom(bars, "Critical") == "Lowest headroom: CPU Requests (40.0%)"
    assert describe_tightest_headroom(bars, "Healthy") is None
    assert describe_tightest_headroom(bars, "Unknown") is None
    assert describe_tightest_headroom(bars, "Overcommitted") is None

    zero_budget = build_tenant_allocation_bars(_summary(cpu_budget="0", cpu_used="0"))
    assert describe_tightest_headroom(zero_budget, "Exhausted") == "Exhausted: CPU Requests (zero governed budget)"

    no_bounded = build_tenant_allocation_bars(_summary(cpu_budget=None))
    assert describe_tightest_headroom(no_bounded[:1], "Near Capacity") is None


def test_contribution_filter_disambiguates_tenants_with_the_same_display_name() -> None:
    first = SimpleNamespace(id="tenant-111111", name="tenant-uat-demo", provider_key="native_kubernetes", ownership_status="adopted")
    second = SimpleNamespace(id="tenant-222222", name="tenant-uat-demo", provider_key="native_kubernetes", ownership_status="adopted")
    rows = _partition_tenant_contributions(
        [first, second],
        [_namespace(first.id, "alpha-ns"), _namespace(second.id, "beta-ns")],
        {},
        [],
    )

    assert len(filter_tenant_contribution_rows(rows, "tenant-uat-demo")) == 2
    assert [item["tenant"].id for item in filter_tenant_contribution_rows(rows, "222222")] == [second.id]
    assert [item["tenant"].id for item in filter_tenant_contribution_rows(rows, "beta-ns")] == [second.id]
    assert len(filter_tenant_contribution_rows(rows, "  DEVELOPMENT  ")) == 2
    assert filter_tenant_contribution_rows(rows, "not-found") == []
    assert filter_tenant_contribution_rows(rows, "") == rows


def test_contribution_summary_uses_unfiltered_committed_tenant_rows() -> None:
    created = SimpleNamespace(
        id="created", name="Created", provider_key="native_kubernetes", ownership_status="managed"
    )
    shared = SimpleNamespace(id="capsule", name="Capsule", provider_key="capsule", ownership_status="adopted")
    ambiguous = SimpleNamespace(id="ambiguous", name="Unknown", provider_key="capsule", ownership_status="adopted")
    rows = _partition_tenant_contributions(
        [created, shared, ambiguous],
        [_namespace("created", "created-ns"), _namespace("capsule", "one"), _namespace("capsule", "two"),
         _namespace("ambiguous", "unknown-ns")],
        {"capsule": {"requests.cpu": "4", "requests.memory": "8Gi", "pods": "20", "requests.storage": "10Gi"}},
        ["ambiguous"],
    )
    assert summarize_tenant_contributions(rows) == {
        "tenants": 3,
        "namespaces": 4,
        "shared": 1,
        "attention": 1,
    }
    assert summarize_tenant_contributions(filter_tenant_contribution_rows(rows, "created"))["tenants"] == 1
    assert summarize_tenant_contributions([]) == {
        "tenants": 0,
        "namespaces": 0,
        "shared": 0,
        "attention": 0,
    }


def test_redesigned_contributions_modal_keeps_header_summary_and_search_outside_scroll_region() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    page = (root / "app/templates/kubernetes/tenant/partials/_tenant_allocation_overview.html").read_text(
        encoding="utf-8"
    )
    routes = (root / "app/kubernetes/tenant/routes.py").read_text(encoding="utf-8")
    docs = (root / "docs/architecture/kubernetes-tenant-capacity-governance.md").read_text(encoding="utf-8")

    analytics = page[page.index('<a href="{{ url_for(\'analytics.capacity\') }}"'):].split("</a>", 1)[0]
    assert "action_button.classes" not in analytics
    assert "hover:underline" in analytics
    assert "current_user.has_permission('analytics.view')" in page

    summary = page[page.index('aria-label="Committed Tenant allocation summary"'):].split("</section>", 1)[0]
    assert "allocation_tenant_summary.tenants" in summary
    assert "allocation_tenant_summary.namespaces" in summary
    assert "allocation_tenant_summary.shared" in summary
    assert "allocation_tenant_summary.attention" in summary

    dialog = page[page.index('<dialog id="{{ contributions_dialog_id }}"'):].split("</dialog>", 1)[0]
    assert dialog.index('aria-label="Committed Tenant allocation summary"') < dialog.index(
        'id="{{ contributions_body_id }}"'
    )
    assert dialog.index('Tenant Registry') < dialog.index('id="{{ contributions_body_id }}"')
    assert dialog.index('role="search"') < dialog.index('tabindex="0"')
    assert "registry_ui.footer" not in dialog
    assert "allocation_tenant_pagination" not in dialog
    assert 'aria-label="Scroll through Tenant contributions"' in dialog
    assert "<table" not in dialog
    assert "<thead" not in dialog
    assert "min-w-[900px]" not in dialog
    assert 'aria-label="Committed Tenant contributions"' in dialog
    assert "md:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]" in dialog
    assert "overflow-y-auto overscroll-contain" in dialog
    assert "data-kaori-native-dialog" in dialog
    assert "data-kaori-dialog-close" in dialog
    assert "table_label.status_label(row.tenant.ownership_status|title" in dialog
    assert "role=\"status\"" in dialog
    assert "Tenant Registry" in dialog
    assert "summarize_tenant_contributions(tenant_rows)" in routes
    assert "context['allocation_tenant_rows'] = tenant_rows" in routes
    assert "context['allocation_tenant_matches'] = len(tenant_rows)" in routes
    assert "paginate_sequence(\n            tenant_rows" not in routes
    assert routes.index("summarize_tenant_contributions(tenant_rows)") < routes.index(
        "filter_tenant_contribution_rows(tenant_rows, allocation_search)"
    )
    assert "committed contribution ledger" in docs


def test_tenant_contributions_stacked_list_exposes_request_metrics_and_namespace_details() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    page = (root / "app/templates/kubernetes/tenant/partials/_tenant_allocation_overview.html").read_text(
        encoding="utf-8"
    )
    dialog = page[page.index('<dialog id="{{ contributions_dialog_id }}"'):].split("</dialog>", 1)[0]
    assert "<ol " in dialog and "<li " in dialog
    assert "<article " in dialog and "<dl " in dialog
    assert "min-w-[900px]" not in dialog
    assert "overflow-x-auto" not in dialog
    assert "allocation_tenant_summary.tenants" in dialog
    assert "allocation_tenant_summary.attention" in dialog
    assert 'row.tenant.id|string|truncate(24' in dialog
    assert "title=\"Tenant ID: {{ row.tenant.id }}\"" in dialog
    assert "row.source" in dialog
    assert "row.tenant.provider_key" in dialog
    assert "View {{ row.namespace_count }} Namespace" in dialog
    assert '<details class="group mt-2">' in dialog
    for dimension in ("CPU Requests", "Memory Requests", "Pod Slots", "Logical Storage"):
        assert dimension in dialog
    for key in ("cpu", "memory", "pods", "storage"):
        assert "row.allocation." + key in dialog
    assert 'hx-target="#{{ contributions_body_id }}"' in dialog
    assert 'hx-select="#{{ contributions_body_id }}"' in dialog
    assert 'hx-swap="outerHTML"' in dialog
    assert 'role="search"' in dialog
    assert "registry_ui.footer" not in dialog
    assert "data-kaori-native-dialog" in dialog
    assert "data-kaori-dialog-open" in page
    assert "data-kaori-dialog-close" in dialog


def test_allocation_modal_htmx_contract_preserves_dialog_during_scrollable_search() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    page = (root / "app/templates/kubernetes/tenant/partials/_tenant_allocation_overview.html").read_text(
        encoding="utf-8"
    )
    routes = (root / "app/kubernetes/tenant/routes.py").read_text(encoding="utf-8")

    assert 'hx-trigger="change"' in page
    assert "View Allocation</button>" not in page
    assert "action_button.classes('secondary')" in page
    assert "How allocation budgets work" in page
    assert "data-kaori-native-dialog" in page
    assert "data-kaori-dialog-open" in page
    assert "data-kaori-dialog-close" in page
    assert 'hx-target="#{{ contributions_body_id }}"' in page
    assert 'hx-select="#{{ contributions_body_id }}"' in page
    assert 'hx-indicator="#{{ contributions_loading_id }}"' in page
    assert 'hx-sync="closest section:replace"' in page
    assert "registry_ui.filter_form" not in page
    assert "registry_ui.footer" not in page
    assert "allocation_page" not in page
    assert "allocation_per_page" not in page
    assert 'row.tenant.id|string|truncate' in page
    assert "allocation_tenant_total" in page
    assert "allocation_search" in routes
    assert "filter_tenant_contribution_rows(tenant_rows, allocation_search)" in routes
    assert "allocation_tenant_pagination" not in routes
    assert "allocation_per_page" not in routes
    assert "context['capacity_pagination'] = capacity_pagination" in routes


def test_scrollable_contribution_ledger_preserves_all_fifty_rows_and_search() -> None:
    # No modal pagination: list and search must both operate on all committed Tenant rows.
    tenants = [
        SimpleNamespace(
            id=f"tenant-{index:02d}",
            name=f"tenant-demo-{index:02d}",
            provider_key="native_kubernetes",
            ownership_status="adopted",
        )
        for index in range(50)
    ]
    namespaces = [_namespace(tenant.id, f"namespace-{index:02d}") for index, tenant in enumerate(tenants)]
    rows = _partition_tenant_contributions(tenants, namespaces, {}, [])
    assert len(rows) == 50
    assert len(filter_tenant_contribution_rows(rows, "")) == 50
    assert [row["tenant"].id for row in filter_tenant_contribution_rows(rows, "tenant-demo-49")] == [
        "tenant-49"
    ]
    assert summarize_tenant_contributions(rows)["tenants"] == 50


def test_tenant_allocation_overview_template_parses_with_jinja() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    template = (root / "app/templates/kubernetes/tenant/partials/_tenant_allocation_overview.html").read_text(
        encoding="utf-8"
    )
    Environment(autoescape=True).parse(template)
    assert 'id="{{ overview_id }}"' in template
    assert "allocation_overview.bars" in template
    assert "row.namespaces" in template
    assert "registry_ui.footer" not in template
    assert 'tabindex="0"' in template
    assert "analytics.capacity" in template
    assert "actual workload utilization" in template


def test_released_generations_are_history_not_active_committed_tenant_contributions() -> None:
    old = [
        SimpleNamespace(
            id=f"tenant-gen-{generation}",
            name="tenant-uat-demo",
            lifecycle_status="released",
            provider_key="native_kubernetes",
            ownership_status="adopted",
        )
        for generation in (1, 2)
    ]
    current = SimpleNamespace(
        id="tenant-gen-3",
        name="tenant-uat-demo",
        lifecycle_status="ready",
        provider_key="native_kubernetes",
        ownership_status="adopted",
    )
    namespaces = [
        _namespace(old[0].id, "tenant-uat-demo", cpu="2"),
        _namespace(old[1].id, "tenant-uat-demo", cpu="2"),
        _namespace(current.id, "tenant-uat-demo", cpu="2"),
    ]
    # Historical generation rows stay preserved for audit, even if a stale
    # Namespace status was not updated in sync with its Released Tenant.
    namespaces[0].provisioning_status = "released"
    namespaces[1].provisioning_status = "ready"
    rows = _partition_tenant_contributions([*old, current], namespaces, {}, [])
    assert len(rows) == 1
    assert rows[0]["tenant"].id == current.id
    assert rows[0]["namespace_count"] == 1
    assert rows[0]["allocation"]["cpu"] == "2.00 cores"
    assert summarize_tenant_contributions(rows) == {
        "tenants": 1, "namespaces": 1, "shared": 0, "attention": 0
    }


def test_terminal_namespaces_excluded_but_failed_and_detached_profiles_still_commit() -> None:
    tenant = SimpleNamespace(
        id="active",
        name="Active",
        lifecycle_status="degraded",
        provider_key="native_kubernetes",
        ownership_status="adopted",
    )
    released = _namespace("active", "old-generation", cpu="8")
    released.provisioning_status = "released"
    deleted = _namespace("active", "deleted", cpu="4")
    deleted.provisioning_status = "deprovisioned"
    detached = _namespace("active", "still-committed", cpu="2")
    detached.resource_profile_id = None  # Missing profile link does not release frozen quota.
    detached.provisioning_status = "failed"
    rows = _partition_tenant_contributions(
        [tenant], [released, deleted, detached], {}, []
    )
    assert len(rows) == 1
    assert rows[0]["namespace_count"] == 1
    assert rows[0]["allocation"]["cpu"] == "2.00 cores"
    assert rows[0]["namespaces"][0]["name"] == "still-committed"


def test_terminal_capsule_generation_does_not_count_historical_shared_quota() -> None:
    old = SimpleNamespace(
        id="capsule-released", name="same", lifecycle_status="released",
        provider_key="capsule", ownership_status="adopted",
    )
    active = SimpleNamespace(
        id="capsule-current", name="same", lifecycle_status="ready",
        provider_key="capsule", ownership_status="adopted",
    )
    shared = {
        old.id: {"requests.cpu": "10", "requests.memory": "10Gi", "pods": "40", "requests.storage": "40Gi"},
        active.id: {"requests.cpu": "4", "requests.memory": "8Gi", "pods": "20", "requests.storage": "12Gi"},
    }
    rows = _partition_tenant_contributions(
        [old, active],
        [_namespace(old.id, "shared"), _namespace(active.id, "shared")],
        shared,
        [],
    )
    assert len(rows) == 1
    assert rows[0]["tenant"].id == active.id
    assert rows[0]["source"] == "Shared Tenant Quota"
    assert rows[0]["allocation"]["cpu"] == "4.00 cores"


def test_tenant_contribution_modal_uses_one_segmented_summary_and_unboxed_metrics() -> None:
    """Readable bordered records without recursively boxed summary and quota cards."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    page = (root / "app/templates/kubernetes/tenant/partials/_tenant_allocation_overview.html").read_text(
        encoding="utf-8"
    )
    Environment(autoescape=True).parse(page)
    dialog = page.split('<dialog id="{{ contributions_dialog_id }}"', 1)[1].split("</dialog>", 1)[0]
    summary = dialog.split('aria-label="Committed Tenant allocation summary"', 1)[1].split(
        "</section>", 1
    )[0]
    scroll = dialog.split('aria-label="Scroll through Tenant contributions"', 1)[1]
    record = scroll.split('aria-label="{{ row.tenant.name }} allocation"', 1)[1].split(
        '</article>', 1
    )[0]

    # Only one enclosing summary surface; thin separators between four facts.
    assert 'grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-outline-subtle' in summary
    assert 'bg-outline-subtle sm:grid-cols-4' in summary
    assert 'min-w-0 bg-surface-card px-3 py-2.5' in summary
    assert 'shadow-sm' not in summary
    assert 'tabular-nums leading-6 text-content-primary' in summary

    # One outer border per record, not another four outlined quota tiles.
    assert '<ol class="space-y-3"' in scroll
    assert '<li class="min-w-0">' in scroll
    assert 'rounded-lg border border-outline-default bg-surface-card p-4' in scroll
    assert 'md:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]' in scroll
    assert 'grid min-w-0 grid-cols-2 gap-x-4 gap-y-3 self-center md:border-l' in record
    assert '<div class="min-w-0">' in record
    assert 'rounded-lg border border-outline-subtle bg-surface-elevated' not in record
    assert 'data-lucide="layers-3"' not in record
    assert 'shadow-sm' not in scroll

    # Read-only evidence, disclosure and HTMX behavior are still canonical.
    assert 'View {{ row.namespace_count }} Namespace' in record
    assert 'title="Tenant ID: {{ row.tenant.id }}"' in record
    assert "row.unknown" in record
    for metric in ('cpu', 'memory', 'pods', 'storage'):
        assert 'row.allocation.' + metric in record
    assert 'tabindex="0"' in dialog
    assert 'hx-target="#{{ contributions_body_id }}"' in dialog
    assert 'hx-select="#{{ contributions_body_id }}"' in dialog
    assert 'overflow-y-auto overscroll-contain' in dialog
    assert 'data-kaori-dialog-close' in dialog
    assert "registry_ui.footer" not in dialog
    assert "<table" not in dialog


def test_tenant_contribution_scroll_frame_and_fixed_evidence_footer() -> None:
    """#1153: room around overflowing rows and a separate non-paginated footer."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    page = (root / "app/templates/kubernetes/tenant/partials/_tenant_allocation_overview.html").read_text(
        encoding="utf-8"
    )
    Environment(autoescape=True).parse(page)
    dialog = page.split('<dialog id="{{ contributions_dialog_id }}"', 1)[1].split("</dialog>", 1)[0]
    swapped_body = dialog.split('<section id="{{ contributions_body_id }}"', 1)[1].split(
        '</footer>', 1
    )[0]
    frame = swapped_body.split('aria-label="Scroll through Tenant contributions"', 1)[0]
    footer = swapped_body.split('<footer ', 1)[1]

    assert 'flex min-h-0 flex-1 flex-col bg-surface-card px-4 py-3 sm:px-6 sm:py-4' in frame
    assert 'min-h-0 flex-1 overflow-y-auto overscroll-contain rounded-xl border border-outline-subtle' in frame
    assert 'bg-surface-elevated px-3 py-3 pr-4' in frame
    assert 'sm:px-4 sm:py-4 sm:pr-5' in frame
    assert 'tabindex="0"' in swapped_body
    assert '<ol class="space-y-3"' in swapped_body
    assert 'shrink-0 flex-wrap items-center justify-between gap-2 border-t border-outline-subtle' in footer
    assert 'bg-surface-elevated px-4 py-3 sm:px-6' in footer
    assert 'aria-label="Tenant Contributions evidence footer"' in footer
    assert 'Read-only committed allocation evidence' in footer
    assert '{{ allocation_tenant_matches }} of {{ allocation_tenant_total }} Tenants' in footer

    # The count updates inside the same HTMX-swapped body as search and scroll.
    assert 'hx-target="#{{ contributions_body_id }}"' in swapped_body
    assert 'hx-select="#{{ contributions_body_id }}"' in swapped_body
    assert dialog.count('<footer ') == 1
    assert 'registry_ui.footer' not in dialog
    assert 'pagination' not in footer.lower()
    assert 'data-kaori-dialog-close' in dialog


def test_tenant_contributions_registry_link_sits_after_description_not_beside_close() -> None:
    """#1153: one responsive lightweight link at the end of the header guidance."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    page = (root / "app/templates/kubernetes/tenant/partials/_tenant_allocation_overview.html").read_text(
        encoding="utf-8"
    )
    Environment(autoescape=True).parse(page)
    dialog = page.split('<dialog id="{{ contributions_dialog_id }}"', 1)[1].split("</dialog>", 1)[0]
    header = dialog.split("<header ", 1)[1].split("</header>", 1)[0]
    guidance = header.split('id="{{ contributions_dialog_id }}-description"', 1)[1].split("</p>", 1)[0]
    closing_controls = header.split("</p>", 1)[1]

    assert 'Governed Namespace requests; Capsule shared quota counted once per Tenant.' in guidance
    assert 'url_for(\'tenant.tenants\', section=\'registry\')' in guidance
    assert guidance.index("Governed Namespace requests") < guidance.index("Tenant Registry")
    assert 'flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1' in guidance
    assert 'aria-label="Open Tenant Registry"' in guidance
    assert '<a href=' not in closing_controls
    assert 'data-kaori-dialog-close' in closing_controls
    assert header.count('aria-label="Open Tenant Registry"') == 1
    assert dialog.count('data-kaori-dialog-close') == 1
    assert 'id="{{ contributions_body_id }}"' in dialog
    assert 'aria-label="Scroll through Tenant contributions"' in dialog
