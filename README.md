# SIVOP Paie

Application web de paie (Côte d'Ivoire) : FastAPI + PostgreSQL + Vue 3. Remplace le logiciel Delphi/SQL Server.
Même architecture et mêmes conventions que vusine-dev.

## Lot 0 (socle)
Connexion par matricule, rôles et permissions, mot de passe imposé à la première connexion,
anti force brute, journal d'audit non modifiable, chiffrement des champs sensibles, administration des comptes.

## Démarrage dev
    cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    cp .env.example .env   # renseigner les clés
    ./scripts/reset_paiedb_dev.sh
    .venv/bin/python -m scripts.create_admin
    .venv/bin/uvicorn app.main:app --port 8005 --reload
    cd ../frontend && npm install && npm run dev      # http://localhost:5178

Tests : `cd backend && .venv/bin/pytest` (base `paiedb_test`).
