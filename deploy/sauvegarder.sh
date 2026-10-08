#!/usr/bin/env bash
# Sauvegarde la base (la clé ENCRYPTION_KEY doit être sauvegardée À PART : sans elle, RIB/CNPS illisibles).
set -euo pipefail
DIR="${BACKUP_DIR:-/opt/paie/backups}"; mkdir -p "$DIR"
URL="$(grep ^DATABASE_URL /opt/paie/backend/.env | cut -d= -f2-)"
pg_dump "$URL" | gzip > "$DIR/paiedb_$(date +%Y%m%d_%H%M%S).sql.gz"
find "$DIR" -name 'paiedb_*.sql.gz' -mtime +30 -delete
