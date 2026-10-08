#!/usr/bin/env bash
# Recrée le schéma de paiedb_dev (DESTRUCTIF, dev uniquement).
set -euo pipefail
URL="${1:-postgresql://paie:paie_test_pw@localhost:5432/paiedb_dev}"
case "$URL" in *dev*) ;; *) echo "Refusé : l'URL doit viser une base de dev."; exit 1;; esac
psql "$URL" -v ON_ERROR_STOP=1 -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
psql "$URL" -v ON_ERROR_STOP=1 -f "$(dirname "$0")/schema.sql" -f "$(dirname "$0")/params.sql"
