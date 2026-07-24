from __future__ import annotations

from celery import shared_task

from app.inventory.schedule import dispatch_due_inventory_sync


@shared_task(name='app.inventory.tasks.dispatch_scheduled_inventory_sync')
def dispatch_scheduled_inventory_sync_task() -> dict[str, object]:
    return dispatch_due_inventory_sync()
