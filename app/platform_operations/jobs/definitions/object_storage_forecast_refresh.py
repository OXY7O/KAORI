from app.platform_operations.jobs.registry import get_job_definition

OBJECT_STORAGE_FORECAST_REFRESH_DEFINITION = get_job_definition('object_storage.forecast.materialize')
