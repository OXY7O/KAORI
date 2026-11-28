from flask import Flask

from app.commands.admin import bootstrap_admin, reset_admin_password
from app.commands.authentication import cleanup_pending_mfa_command, recover_bot_protection_command
from app.commands.automation_inventory import automation_inventory_store
from app.commands.automation_remote_review import automation_remote_review_check
from app.commands.integrations import refresh_integration_runtime_command
from app.commands.internal_pki import import_internal_pki, prepare_internal_pki
from app.commands.openbao import collect_openbao_inventory, register_internal_openbao
from app.commands.rbac import seed_rbac
from app.commands.reports import run_report_schedules
from app.commands.retention import archive_retention
from app.commands.secret_store import bootstrap_secret_store, qualify_openbao, secret_store_status, verify_secret_store
from app.infrastructure_automation.cli import automation_localhost_probe


def register_commands(app: Flask) -> None:
    app.cli.add_command(bootstrap_admin)
    app.cli.add_command(reset_admin_password)
    app.cli.add_command(cleanup_pending_mfa_command)
    app.cli.add_command(recover_bot_protection_command)
    app.cli.add_command(seed_rbac)
    app.cli.add_command(run_report_schedules)
    app.cli.add_command(archive_retention)
    app.cli.add_command(refresh_integration_runtime_command)
    app.cli.add_command(import_internal_pki)
    app.cli.add_command(prepare_internal_pki)
    app.cli.add_command(secret_store_status)
    app.cli.add_command(verify_secret_store)
    app.cli.add_command(bootstrap_secret_store)
    app.cli.add_command(qualify_openbao)
    app.cli.add_command(register_internal_openbao)
    app.cli.add_command(collect_openbao_inventory)
    app.cli.add_command(automation_localhost_probe)
    app.cli.add_command(automation_inventory_store)
    app.cli.add_command(automation_remote_review_check)
