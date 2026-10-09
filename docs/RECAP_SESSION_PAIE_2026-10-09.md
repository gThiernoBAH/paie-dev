# SIVOP Paie — Récapitulatif de session du 9 octobre 2026

Projet : FastAPI + SQLAlchemy 2 + PostgreSQL (backend) · Vue 3 `<script setup>` + Vite + lucide-vue-next (frontend).
Remplace l'ancien logiciel Delphi / SQL Server (`github.com/gThiernoBAH/legacy_paie`).
Dépôt de développement : `https://github.com/gThiernoBAH/paie-dev`

---

## 1. Livrables de la session

| Patch | Contenu | Fichiers | Tests |
|---|---|---|---|
| `sivop-paie-patch-octobre-2026.tar.gz` | Menus, boutons, prêts, fiche salarié, statistiques, outils de gestion, logo | 50 | 259 réussis, 2 attendus en échec |
| `sivop-paie-patch-lot12.tar.gz` | Onglet Masse salariale, clôture annuelle, grille salariale, bulletin paramétrable | 29 | 276 réussis, 2 attendus en échec |

Ordre d'application : octobre, puis Lot 12.

### Installation (pour chaque patch)
1. `pg_dump` de la base (sauvegarde).
2. `tar xzf <patch>.tar.gz --strip-components=1` à la racine du projet.
3. `psql -f backend/scripts/schema.sql` puis `psql -f backend/scripts/params.sql` (idempotents).
4. Patch d'octobre uniquement : `cd frontend && npm install` (ajoute `chart.js`).
5. Relancer le backend, se reconnecter.

Incidents rencontrés à l'installation :
- `Failed to resolve import "chart.js"` : `npm install` non fait.
- `column evolutions_salaire.lot_id does not exist` : `schema.sql` non rejoué.

---

## 2. Patch d'octobre 2026

**Interface**
- Menu : ordre Paie, Règlements, Personnel, Pilotage, Configuration ; un seul groupe ouvert à la fois (accordéon).
- Congés : boutons Approuver / Refuser / Annuler / Reprendre un solde en icônes avec infobulle.
- Administration, Utilisateurs : « Droits » et « Réinitialiser » (infobulle « Réinitialiser le mot de passe »).
- Prêts :
  - colonne « Montant » alignée ;
  - échéancier avec statuts : prévue, prélevée sur paie, réglée hors paie, passée en perte ;
  - règlement manuel d'une échéance et annulation de ce règlement ;
  - clôture d'un prêt (départ, démission, décès, licenciement, autre), passé en perte ou régularisé hors paie ;
  - les retenues déjà préparées sont retirées de la paie ; la campagne à recalculer est signalée.
- Fiche salarié :
  - onglets Fiche, Personnes à charge, Rubriques fixes, Historique et dossier ;
  - historique des mutations (service, section, emploi, catégorie, site, contrat, salaire) avec date d'effet et motif ;
  - accès espace salarié : détection d'un accès existant, « Créer l'accès espace salarié », « Réinitialiser ».
- Tableau de bord, Statistiques : effectifs (sexe, tranches d'âge corrigées, ancienneté, contrats, services, sections, emplois, catégories, absences), graphiques Chart.js.
- Personnel, Augmentations : augmentation en masse (% ou montant fixe), aperçu, lots annulables.
- Paie, Simulation de bulletin : calcul hypothétique, rien n'est enregistré.
- Rapports : liste du personnel, situation de famille, journaux (présences, congés, rubriques, prêts), bulletins à contrôler, cumuls annuels.
- Logo : déposer `backend/app/assets/logo.png` (ou variable `LOGO_PATH`) ; il apparaît sur les bulletins et les lettres.

**Congés** : paramètre `conges_mode_paiement` (`maintien_salaire` par défaut, ou `indemnite_conges`) et `conges_majoration_indemnite`.

---

## 3. Patch Lot 12

**Tableau de bord** : trois onglets — Vue d'ensemble, **Masse salariale** (réalisé, prêts, indicateurs du prévisionnel), Statistiques (effectifs, absences, graphique « Coût employeur annuel prévisionnel par service »).

**Clôture annuelle** (menu Paie)
- Prérequis : toutes les campagnes de l'année sont validées.
- À la clôture : campagnes passées à « clôturée », cumuls par salarié figés (instantané), année verrouillée (campagne, réouverture de campagne, salaire daté, augmentation, règlement ou clôture de prêt datés).
- Réouverture : administrateur uniquement, motif obligatoire, tracée dans le journal d'audit.

**Grille salariale** (menu Configuration)
- Règle reprise du legacy : salaire mensuel = base horaire de la catégorie × heures de la tranche × coefficient, arrondi au franc.
- Cinq tranches horaires modifiables. Valeurs de départ **déduites des captures du legacy** (173,33 / 193,2632 / 198,2461 / 213,196 / 99,6646 heures) : à confirmer.
- Base horaire par catégorie, datée : saisie manuelle ou import d'un tableau collé (colonnes CATEGORIE et BASE HEURE, ou SALAIRE MENSUEL TRANCHE 1 pour déduire la base), avec aperçu.
- Fiche salarié : champ « Tranche horaire » et avertissement si le salaire catégoriel est sous la grille. Rapport « Salariés et grille salariale ».
- Paramètre `grille_blocage_sous_minimum` (désactivé par défaut) pour refuser un salaire sous la grille.
- La grille ne modifie jamais un salaire.

**Bulletin paramétrable** (Paramétrage, catégorie « Bulletin de paie »)
Cumuls annuels, solde de congés, charges patronales, net en lettres, mode de paiement, bloc emploi/catégorie/service, mention de bas de page, pied de page libre (un tiret = rien), hauteur du logo. Les valeurs d'origine reproduisent le bulletin précédent.

---

## 4. Décision : « Salaire réel / hors salaire »

Non repris. Le legacy stockait un « salaire confidentiel » (`SALREEL`) et calculait `HORSAL = SALREEL − (salaire catégoriel + sursalaire)`, dans un registre à part, jamais porté sur le bulletin : c'est la part payée hors déclaration CNPS et ITS.

Équivalents légitimes proposés, **à décider** :
- contrôle « salaire du contrat » contre « bulletin » ;
- suivi des avantages en nature et des remboursements de frais, avec plafonds et justificatifs ;
- coût complet employeur (déjà présent dans les statistiques).

---

## 5. Points à confirmer

- Tranches horaires : heures déduites des captures (probables régimes d'horaires hebdomadaires ; la tranche 5 ressemble à un mi-temps).
- Mode de paiement des congés : `maintien_salaire` par défaut, en « à confirmer » (cabinet ou convention collective).
- Bulletin : éléments à afficher ou masquer, à valider en séance avec le service de la paie.
- Clôture annuelle : limitée aux cumuls figés et au verrou ; pas de pièces comptables de clôture.
- Mise en page libre du bulletin : non faite (réglages seulement).

---

## 6. Prochaine session — Lot 12 bis : reprise des données SQL Server

Objectif : migrer les données de l'ancien logiciel vers PostgreSQL.

À préparer :
1. Accès à une sauvegarde (`.bak`) ou à un export des tables du legacy. Voir `SqlUnit.pas` dans le dépôt legacy pour les noms de tables et de colonnes.
2. Périmètre : référentiels (services, sections, emplois, catégories, sites, banques, contrats), salariés (dont `TRANCHE`, situation de famille, enfants), historique des salaires, bases horaires par catégorie, congés et soldes, prêts, historique des bulletins si repris.
3. Règles à fixer : matricules (6 chiffres), RIB et n° CNPS (chiffrés à l'import), salaires datés, doublons, salariés sortis.
4. Méthode proposée : scripts de reprise rejouables, avec mode « à blanc » (aperçu et anomalies sans écrire), puis import réel, puis rapport d'écarts (effectifs, masses salariales, soldes).
5. Hors périmètre : la colonne `SALREEL` du legacy (voir section 4).
6. Données de la grille salariale : export de la table des catégories et tranche actuelle de chaque salarié.

---

## 7. Rappels techniques

- Tests : `cd backend && python -m pytest tests -q` (base `paiedb_test` ; `schema.sql` et `params.sql` rechargés à chaque session et à chaque test).
- Compteur de paramètres dans `tests/test_parametres.py` : 95.
- Salaires visibles seulement avec le droit `voir_donnees_sensibles` ; agrégats avec `voir_rapports`.
- Bulletins validés inaltérables (trigger base) ; un exercice clôturé verrouille les écritures datées.
- Idempotence : `schema.sql` et `params.sql` se rejouent sans risque.
