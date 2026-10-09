# Lot 12 — clôture annuelle, grille salariale, bulletin paramétrable

## Tableau de bord
Trois onglets : **Vue d'ensemble**, **Masse salariale** (masse réalisée, prêts, prévisionnel annuel), **Statistiques** (effectifs, absences, et le graphique « Coût employeur annuel prévisionnel par service »). Les filtres année et service s'appliquent aux deux derniers.

## Clôture annuelle (Paie → Clôture annuelle)
- Prérequis : toutes les campagnes de l'année sont validées.
- À la clôture : les campagnes validées passent à « clôturée », les cumuls par salarié sont figés (consultables, exportables), et l'année est verrouillée : plus de nouvelle campagne, de réouverture de campagne, de salaire daté, d'augmentation ni de règlement ou clôture de prêt daté dans cette année.
- Réouverture : administrateur uniquement, motif obligatoire, tracée dans le journal d'audit.

## Grille salariale (Configuration → Grille salariale)
Reprise du principe de l'ancien logiciel : **salaire mensuel = base horaire de la catégorie × heures de la tranche × coefficient**, arrondi au franc.
- 5 tranches horaires (heures et coefficient modifiables). Valeurs de départ **déduites** des captures du legacy (173,33 / 193,2632 / 198,2461 / 213,196 / 99,6646 heures) : **à confirmer** avec la paie.
- Base horaire par catégorie, datée ; saisie à la main ou **import** d'un tableau copié depuis le legacy (colonnes CATEGORIE et BASE HEURE, ou SALAIRE MENSUEL TRANCHE 1 pour déduire la base). Aperçu avant application.
- Fiche salarié : champ « Tranche horaire » ; avertissement si le salaire catégoriel est sous la grille. Rapport « Salariés et grille salariale ».
- Paramètre `grille_blocage_sous_minimum` (non par défaut) : refuse un salaire inférieur à la grille.
- La grille ne modifie jamais un salaire : c'est une référence.

## Bulletin paramétrable (Paramétrage → Bulletin de paie)
Cumuls annuels, solde de congés, charges patronales, net en lettres, mode de paiement, bloc emploi/catégorie/service, mention de bas de page, pied de page libre (un tiret = rien), hauteur du logo. Les valeurs d'origine reproduisent le bulletin actuel. À revoir en séance avec le service de la paie.

## Installation
1. `pg_dump` ; 2. extraire le tar (`--strip-components=1`) ; 3. `psql -f backend/scripts/schema.sql` puis `params.sql` ; 4. relancer le backend (aucune nouvelle dépendance frontend).
