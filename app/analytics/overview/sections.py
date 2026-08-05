from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OverviewSection:
    template: str
    hydration: str


OVERVIEW_SECTIONS: dict[str, OverviewSection] = {
    'health-summary': OverviewSection(
        template='analytics/overview/partials/_health_summary.html',
        hydration='composite',
    ),
    'resource-snapshot': OverviewSection(
        template='analytics/overview/partials/_resource_snapshot.html',
        hydration='resource',
    ),
    'capacity-snapshot': OverviewSection(
        template='analytics/overview/partials/_capacity_snapshot.html',
        hydration='capacity',
    ),
    'workload-snapshot': OverviewSection(
        template='analytics/overview/partials/_workload_snapshot.html',
        hydration='workload',
    ),
    'storage-snapshot': OverviewSection(
        template='analytics/overview/partials/_storage_snapshot.html',
        hydration='storage',
    ),
    'top-consumers': OverviewSection(
        template='analytics/overview/partials/_top_consumers_snapshot.html',
        hydration='top-consumers',
    ),
    'forecast-snapshot': OverviewSection(
        template='analytics/overview/partials/_forecast_snapshot.html',
        hydration='forecast',
    ),
    'alerts-snapshot': OverviewSection(
        template='analytics/overview/partials/_alerts_snapshot.html',
        hydration='alerts',
    ),
}


def get_overview_section(section: str) -> OverviewSection | None:
    return OVERVIEW_SECTIONS.get(section)
