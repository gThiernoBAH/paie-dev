# Installation sur un serveur local (test)

Prérequis : Linux (ou WSL), **Python 3.12+**, **Node 20+**, **PostgreSQL 15+**.

## 1. Base de données
    sudo -u postgres psql -c "CREATE ROLE paie LOGIN PASSWORD 'choisir-un-mot-de-passe';"
    sudo -u postgres psql -c "CREATE DATABASE paiedb_dev OWNER paie;"
    sudo -u postgres psql -c "CREATE DATABASE paiedb_test OWNER paie;"      # uniquement pour lancer les tests

## 2. Back-end
    cd backend
    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    cp .env.example .env
Éditer `backend/.env` :
- `DATABASE_URL=postgresql://paie:<mot de passe>@localhost:5432/paiedb_dev` (le nom de la base doit contenir « dev » pour le jeu de démonstration)
- `AUTH_SECRET_KEY` : `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`
- `ENCRYPTION_KEY` : `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
  **Sauvegardez cette clé à part : sans elle, les RIB et numéros CNPS chiffrés sont définitivement illisibles.**

Créer le schéma, le compte administrateur, puis (facultatif) les données de démonstration :

    ./scripts/reset_paiedb_dev.sh "postgresql://paie:<mot de passe>@localhost:5432/paiedb_dev"      # DÉTRUIT et recrée la base de dev
    ADMIN_PASSWORD='UnMotDePasseSolide2026' .venv/bin/python -m scripts.create_admin --identifiant admin --nom Administrateur
    ADMIN_PASSWORD='UnMotDePasseSolide2026' .venv/bin/python -m scripts.demo_data       # jeu de démonstration (affiche 3 comptes de test)
    .venv/bin/uvicorn app.main:app --port 8005

Le schéma est idempotent : après une mise à jour du code, rejouer `psql <url> -f scripts/schema.sql -f scripts/params.sql` met la base à niveau sans rien supprimer.

## 3. Front-end
    cd frontend && npm install && npm run dev        # http://localhost:5178  (relaie /api vers le port 8005)

Ouvrir http://localhost:5178 et se connecter avec `admin`. Sur téléphone (même réseau) : `http://<IP du serveur>:5178`.

## 4. E-mail (facultatif pour les tests)
Paramétrage → E-mail : renseigner hôte / port / expéditeur, `email_actif = true` ; le mot de passe du compte SMTP va dans `backend/.env` (`SMTP_PASSWORD=`). Le bouton « Envoyer un message de test » vérifie la configuration. Tant que `email_actif` est faux, rien ne part.

## Problèmes courants
- « Le serveur est injoignable » : l'API n'est pas démarrée sur le port 8005.
- Démarrage refusé « AUTH_SECRET_KEY… » : clé trop courte ou absente dans `.env`.
- Les polices (Google Fonts) ne se chargent pas hors ligne : l'application reste utilisable avec une police système.
