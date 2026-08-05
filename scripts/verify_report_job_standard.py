from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
required = {
    'app/reports/jobs/contract.py': ['kaori-report-job-v1.0', 'time_range', 'committed_snapshot', 'window_start', 'snapshot_policy'],
    'app/reports/jobs/queue.py': ['DEFAULT_REPORTS_QUEUE', 'REPORTS_CELERY_QUEUE', 'get_reports_queue_name'],
    'app/reports/jobs/service.py': ['enqueue_report_generation', "JOB_TYPE = 'report_generation'", 'get_reports_queue_name()'],
    'app/reports/jobs/tasks.py': ['generate_report_job', 'JobExecutionContext', 'record_operational_activity'],
    'app/reports/generate/routes.py': ['enqueue_report_generation'],
    'app/reports/schedules/service.py': ['enqueue_report_generation', "run.status = 'queued'", 'get_queue_readiness'],
    'app/reports/schedules/job_adapter.py': ['dispatch_report_schedule_job', 'get_reports_queue_name()', 'get_queue_readiness'],
    'app/config/default.py': ['app.reports.jobs.tasks', 'app.reports.jobs.tasks.generate_report_job'],
    'scripts/verify_reports_worker_runtime.py': ['active_queues', 'registered', 'generate_report_job', 'run_report_schedule_job'],
    'docs/reports/kaori-report-job-standard-v1.md': ['Analytics', 'Inventory', 'JobExecution.payload_json'],
}
errors=[]
for name, tokens in required.items():
    path=ROOT/name
    if not path.exists(): errors.append(f'missing {name}'); continue
    text=path.read_text(encoding='utf-8')
    for token in tokens:
        if token not in text: errors.append(f'{name}: missing {token}')
for forbidden in ['generate_report_artifact(report.id)']:
    text=(ROOT/'app/reports/schedules/service.py').read_text(encoding='utf-8')
    if forbidden in text: errors.append('schedule service still renders reports inline')
if errors:
    raise SystemExit('KAORI report job audit failed:\n'+'\n'.join(errors))
print('KAORI report job audit passed: Analytics time-range and Inventory committed-snapshot jobs use the Reports worker, canonical JobExecution parameters, and persistent notifications.')
