from app.platform_operations.jobs.registry import get_job_definition

FORECAST_REFRESH_DEFINITION = get_job_definition('analytics.forecast.materialize')
