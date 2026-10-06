#!/bin/sh
set -eu

flask --app run:app db upgrade

if [ "${1:-}" = "--bootstrap-admin" ]; then
    # bootstrap-admin seeds the default RBAC catalog before creating the user.
    flask --app run:app bootstrap-admin
else
    flask --app run:app seed-rbac
fi

echo "Database migration and RBAC initialization completed."

if [ "${1:-}" != "--bootstrap-admin" ]; then
    echo "Run 'flask --app run:app bootstrap-admin' when the first administrator is required."
fi
