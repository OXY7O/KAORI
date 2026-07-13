from flask import Flask

from app.commands.admin import bootstrap_admin, reset_admin_password
from app.commands.auth import cleanup_login_audit
from app.commands.rbac import seed_rbac
from app.commands.reports import run_report_schedules
from app.commands.retention import archive_retention


def register_commands(app: Flask) -> None:
    app.cli.add_command(bootstrap_admin)
    app.cli.add_command(reset_admin_password)
    app.cli.add_command(seed_rbac)
    app.cli.add_command(cleanup_login_audit)
    app.cli.add_command(run_report_schedules)
    app.cli.add_command(archive_retention)
