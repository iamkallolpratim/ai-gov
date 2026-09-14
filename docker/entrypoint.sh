#!/usr/bin/env sh
# Run migrations, seed, sync policies to OPA, then start the API.
set -e

echo "Running database migrations..."
alembic upgrade head

if [ "${SEED_ON_START:-true}" = "true" ]; then
  echo "Seeding baseline data..."
  python scripts/seed.py
fi

if [ "${SYNC_OPA_ON_START:-true}" = "true" ]; then
  echo "Syncing policies to OPA..."
  python scripts/sync_opa.py || echo "OPA sync skipped (OPA unreachable)"
fi

exec "$@"
