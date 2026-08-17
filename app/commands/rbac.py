import click
from flask.cli import with_appcontext

from app.access.rbac.service import seed_default_rbac


@click.command(
    'seed-rbac',
    short_help='Seed default RBAC roles and permissions.',
    help=(
        'Create or update the built-in KAORI RBAC baseline. '
        'This command is idempotent and seeds default roles such as viewer, operator, editor, admin, and auditor, '
        'plus the default permission catalog required by Access, protected routes, and navigation visibility.'
    ),
)
@with_appcontext
def seed_rbac():
    result = seed_default_rbac()
    click.echo(f'RBAC seeded: {result["roles"]} roles, {result["permissions"]} permissions')
