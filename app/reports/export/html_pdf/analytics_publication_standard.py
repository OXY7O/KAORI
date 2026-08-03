from __future__ import annotations

ANALYTICS_PUBLICATION_FAMILY = 'analytics'
ANALYTICS_PUBLICATION_STANDARD = 'kaori-analytics-pdf-v1.0'
ANALYTICS_CANONICAL_REFERENCE = 'analytics-overview-report-34'
ANALYTICS_SHARED_STYLESHEET = 'analytics_publication.css'

ANALYTICS_TEMPLATE_STYLESHEETS: dict[str, str] = {
    'reports/pdf/analytics_overview.html': 'analytics_overview.css',
    'reports/pdf/resource_utilization.html': 'resource_utilization.css',
    'reports/pdf/capacity_analysis.html': 'capacity_analysis.css',
    'reports/pdf/storage_analysis.html': 'storage_analysis.css',
    'reports/pdf/workload_analysis.html': 'workload_analysis.css',
    'reports/pdf/forecast_analysis.html': 'forecast_analysis.css',
    'reports/pdf/top_consumers_analysis.html': 'top_consumers_analysis.css',
    'reports/pdf/alerts_anomalies.html': 'alerts_anomalies.css',
}

ANALYTICS_TEMPLATE_NAMES = tuple(ANALYTICS_TEMPLATE_STYLESHEETS)
