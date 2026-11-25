#!/usr/bin/env bash
# Create a PostgreSQL custom-format dump and a SeaweedFS volume archive.
# The database dump is transactionally consistent. Object storage is quiesced
# by default so the tar archive is not taken while SeaweedFS is writing.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose --project-directory "$ROOT_DIR" --file "$ROOT_DIR/docker-compose.yml")
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
QUIESCE="${QUIESCE:-true}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DB_FILE="$BACKUP_DIR/postgres-$STAMP.dump"
OBJECT_FILE="$BACKUP_DIR/seaweedfs-$STAMP.tar.gz"
MANIFEST="$BACKUP_DIR/manifest-$STAMP.txt"

umask 077
mkdir -p "$BACKUP_DIR"
BACKUP_DIR="$(cd "$BACKUP_DIR" && pwd)"

seaweed_was_running=false
app_was_running=false

restore_services() {
  if [[ "$seaweed_was_running" == true ]]; then
    "${COMPOSE[@]}" start seaweedfs >/dev/null 2>&1 || true
  fi
  if [[ "$app_was_running" == true ]]; then
    "${COMPOSE[@]}" --profile app start app >/dev/null 2>&1 || true
  fi
}
trap restore_services EXIT

if [[ "$QUIESCE" == true ]]; then
  [[ -n "$("${COMPOSE[@]}" ps --status running -q seaweedfs 2>/dev/null || true)" ]] \
    && seaweed_was_running=true
  [[ -n "$("${COMPOSE[@]}" ps --status running -q app 2>/dev/null || true)" ]] \
    && app_was_running=true
  if [[ "$app_was_running" == true || "$seaweed_was_running" == true ]]; then
    echo "Quiescing app and SeaweedFS for a consistent object archive..."
    "${COMPOSE[@]}" stop app seaweedfs >/dev/null 2>&1 || true
  fi
fi

echo "Dumping PostgreSQL..."
"${COMPOSE[@]}" exec -T postgres sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner' \
  > "$DB_FILE"

# Validate the dump before declaring success.
"${COMPOSE[@]}" exec -T postgres pg_restore --list < "$DB_FILE" >/dev/null
[[ -s "$DB_FILE" ]]

echo "Archiving SeaweedFS volume..."
if ! docker inspect atlas-seaweedfs >/dev/null 2>&1; then
  echo "atlas-seaweedfs container not found; cannot archive object storage" >&2
  exit 1
fi
# Stream the archive to a file created by the invoking user. A bind-mounted
# output directory would be written as root by the helper container.
docker run --rm \
  --volumes-from atlas-seaweedfs \
  alpine:3.20 \
  tar -cz -C /data . > "$OBJECT_FILE"
tar -tzf "$OBJECT_FILE" >/dev/null

{
  echo "created_at=$STAMP"
  echo "database=$DB_FILE"
  echo "objects=$OBJECT_FILE"
  echo "database_sha256=$(sha256sum "$DB_FILE" | awk '{print $1}')"
  echo "objects_sha256=$(sha256sum "$OBJECT_FILE" | awk '{print $1}')"
} | tee "$MANIFEST"

echo "Backup complete: $BACKUP_DIR"
