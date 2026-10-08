# Déploiement SIVOP Paie (serveur interne)

Le déploiement réel se fera en session dédiée. Principe : même schéma que vusine-dev.

1. Utilisateur `paie`, code dans `/opt/paie`, base `paiedb` (rôle `paie`).
2. `backend/.env` depuis `deploy/env.prod.example` (chmod 600). Sauvegarder `ENCRYPTION_KEY` à part.
3. `sudo cp deploy/paie-api.service /etc/systemd/system/ && sudo systemctl enable --now paie-api`.
4. `deploy/nginx-paie.conf` dans nginx ; **activer TLS** (certificat interne).
5. Premier admin : `cd backend && .venv/bin/python -m scripts.create_admin`.
6. Mises à jour : tag Git puis `./deploy/deployer.sh vX.Y.Z` (sauvegarde automatique avant).
