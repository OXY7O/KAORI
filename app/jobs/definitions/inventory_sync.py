from app.jobs.registry import get_job_definition

INVENTORY_SYNC_DEFINITION = get_job_definition('kubernetes.inventory.sync')
