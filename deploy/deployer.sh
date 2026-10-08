#!/usr/bin/env bash
# Déploie une version taguée : ./deploy/deployer.sh v0.1.0   (à lancer sur le serveur, dans /opt/paie)
set -euo pipefail
TAG="${1:?Usage: deployer.sh <tag>}"
cd /opt/paie
./deploy/sauvegarder.sh
git fetch --tags && git checkout "$TAG"
cd backend
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
psql "$(grep ^DATABASE_URL .env | cut -d= -f2-)" -v ON_ERROR_STOP=1 -f scripts/schema.sql -f scripts/params.sql
cd ../frontend && npm ci && npm run build
sudo systemctl restart paie-api
curl -fsS http://127.0.0.1:8105/health && echo " OK ($TAG)"
