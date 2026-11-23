#!/bin/sh
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'EOSQL'
SELECT 'CREATE DATABASE atlas_test OWNER "' || current_user || '"'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'atlas_test')\gexec
EOSQL
