#!/bin/sh
set -eu

if [ "${WAIT_FOR_DB:-false}" = "true" ]; then
    python -m scripts.wait_for_db
fi

exec "$@"
