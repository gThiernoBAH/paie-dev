# SIVOP Paie

Application web de paie (Côte d'Ivoire) : **FastAPI + PostgreSQL + Vue 3**. Remplace le logiciel Delphi / SQL Server.
Même architecture, mêmes conventions et même charte graphique que vusine-dev.

## Ce que fait l'application
| Domaine | Contenu |
|---|---|
| Salariés | Fiches, référentiels (services, emplois, catégories, sites…), historique de salaire, sortie, comptes d'accès ; RIB et n° CNPS **chiffrés**, salaire masqué sans droit dédié |
| Pointages | Import quotidien des fichiers de pointeuse (CSV), corrections, calcul automatique des présences (heures normales, HS1 à HS4, dimanche / jours fériés, nuit, absences) |
| Paie | Campagnes mensuelles et par quinzaine (journaliers), rubriques variables, saisie groupée, calcul (CNPS, ITS, CMU, ancienneté, transport…), validation avec blocage, bulletins PDF figés et inaltérables |
| Cas spéciaux | Congés et soldes, prêts / avances prélevés automatiquement, solde de tout compte (congés, licenciement par tranches) |
| Sorties | Virements (lot, fichier Excel/CSV, alerte au lancement), états CNPS / ITS / FDFP / DISA, journal comptable équilibré |
| Communication | Envoi des bulletins par e-mail en PDF protégé, suivi et relance |
| Espace salarié | Bulletins, congés, profil — pensé pour le téléphone, installable (PWA) |
| Pilotage | Tableau de bord, rapports (masse salariale, service, heures sup., effectif, mouvements, livre de paie) |
| Paramétrage | Tous les taux, plafonds, barèmes, comptes comptables, e-mail : datés, tracés, avec statut « confirmé / à confirmer » |
| Sécurité | Rôles + permissions fines, anti force brute, journal d'audit non modifiable, bulletins validés protégés au niveau base de données |

## Documentation
- [`docs/INSTALLATION_LOCALE.md`](docs/INSTALLATION_LOCALE.md) — installer et lancer sur votre serveur local
- [`docs/GUIDE_TEST.md`](docs/GUIDE_TEST.md) — scénarios de test pas à pas (avec le jeu de démonstration)
- [`docs/POINTS_A_CONFIRMER.md`](docs/POINTS_A_CONFIRMER.md) — ce qu'il faut valider avec vous avant la mise en production
- [`docs/MOTEUR.md`](docs/MOTEUR.md) — règles de calcul de la paie
- [`docs/DECLARATIONS.md`](docs/DECLARATIONS.md) — déclarations, virements, comptabilité
- [`deploy/`](deploy/README_DEPLOIEMENT.md) — esquisse de déploiement (finalisé au lot 13)

## Tests automatiques
`cd backend && .venv/bin/pytest` — base jetable `paiedb_test`. Les bulletins réels de référence (matricule 000054, journaliers) sont des tests : le net 205 014 FCFA doit sortir exactement.
