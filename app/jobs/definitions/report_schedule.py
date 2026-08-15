from app.jobs.registry import get_job_definition

REPORT_SCHEDULE_DEFINITION = get_job_definition('reports.schedule.dispatch')
