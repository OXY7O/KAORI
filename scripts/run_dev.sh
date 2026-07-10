#!/bin/sh
set -eu

exec flask \
    --app run:app \
    run \
    --host=0.0.0.0 \
    --port="${KAORI_DEV_PORT:-5000}" \
    --debug
