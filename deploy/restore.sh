#!/usr/bin/env bash
# Restore a backup produced by deploy/backup.sh.
#
# WARNING: this replaces database objects and the SeaweedFS volume. It is
# destructive. Run a restore drill against a scratch database first.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose --project-directory "$ROOT_DIR" --file "$ROOT_DIR/docker-compose.yml")
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
RESTORE_DATABASE="${RESTORE_DATABASE:-}"
RESTORE_OBJECTS="${RESTORE_OBJECTS:-true}"
CONFIRM="${CONFIRM_RESTORE:-}"

if [[ "$CONFIRM" != "yes" ]]; then
  echo "Refusing destructive restore. Set CONFIRM_RESTORE=yes to proceed." >&2
  echo "For a drill, set RESTORE_DATABASE=atlas_restore_test RESTORE_OBJECTS=false." >&2
  exit 2
fi

if [[ ! -d "$BACKUP_DIR" ]]; then
  echo "Backup directory not found: $BACKUP_DIR" >&2
  exit 2
fi

DB_FILE="${DB_FILE:-$(find "$BACKUP_DIR" -maxdepth 1 -name 'postgres-*.dump' -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)}"
OBJECT_FILE="${OBJECT_FILE:-$(find "$BACKUP_DIR" -maxdepth 1 -name 'seaweedfs-*.tar.gz' -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)}"

if [[ -z "$DB_FILE" || ! -s "$DB_FILE" ]]; then
  echo "No non-empty PostgreSQL dump found in $BACKUP_DIR" >&2
  exit 2
fi
if [[ "$RESTORE_OBJECTS" == true && ( -z "$OBJECT_FILE" || ! -s "$OBJECT_FILE" ) ]]; then
  echo "No non-empty SeaweedFS archive found in $BACKUP_DIR" >&2
  exit 2
fi

target_db="${RESTORE_DATABASE:-}"
if [[ -z "$target_db" ]]; then
  target_db="$("${COMPOSE[@]}" exec -T postgres sh -c 'printf %s "$POSTGRES_DB"')"
fi

# Never restore into the source database during a drill.
if [[ "$target_db" == "atlas_test" ]]; then
  echo "Refusing to restore into atlas_test" >&2
  exit 2
fi

echo "Restoring $DB_FILE into database $target_db..."
app_was_running=false
[[ -n "$("${COMPOSE[@]}" ps --status running -q app 2>/dev/null || true)" ]] \
  && app_was_running=true
"${COMPOSE[@]}" stop app >/dev/null 2>&1 || true
"${COMPOSE[@]}" exec -T postgres pg_restore --list < "$DB_FILE" >/dev/null
"${COMPOSE[@]}" exec -T postgres sh -c \
  'createdb -U "$POSTGRES_USER" "$1" 2>/dev/null || true' _ "$target_db"
"${COMPOSE[@]}" exec -T postgres sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$1" --clean --if-exists --no-owner' _ "$target_db" \
  < "$DB_FILE"

if [[ "$RESTORE_OBJECTS" == true ]]; then
  if ! docker inspect atlas-seaweedfs >/dev/null 2>&1; then
    echo "atlas-seaweedfs container not found; cannot restore object storage" >&2
    exit 1
  fi
  echo "Restoring SeaweedFS volume from $OBJECT_FILE..."
  "${COMPOSE[@]}" stop seaweedfs >/dev/null 2>&1 || true
  docker run --rm -i \
    --volumes-from atlas-seaweedfs \
    alpine:3.20 \
    sh -c 'rm -rf /data/* /data/.[!.]* /data/..?* 2>/dev/null || true; tar -xz -C /data' < "$OBJECT_FILE"
  "${COMPOSE[@]}" start seaweedfs >/dev/null
fi

if [[ "$app_was_running" == true ]]; then
  "${COMPOSE[@]}" --profile app start app >/dev/null
fi

echo "Restore complete. Verify the application and run a read-only smoke test."
