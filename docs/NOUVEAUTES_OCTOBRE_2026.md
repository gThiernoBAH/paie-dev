# Évolutions d'octobre 2026

## Interface
- **Menu** : ordre Paie – Règlements – Personnel – Pilotage – Configuration ; ouvrir un groupe referme les autres.
- **Boutons à icônes** (avec infobulle) pour Approuver / Refuser / Annuler un congé et « Reprendre un solde » ; en Administration → Utilisateurs : « Droits » et « Réinitialiser » (infobulle « Réinitialiser le mot de passe »).
- **Prêts** : colonne « Montant » alignée ; échéancier avec statut (Prévue, Prélevée sur paie, Réglée hors paie, Passée en perte), date de règlement, action « Régler » / « Annuler le règlement » ; **clôture d'un prêt** (départ, démission, décès, licenciement, autre) soit passé en perte, soit régularisé hors paie. Les retenues déjà préparées sont retirées de la paie ; si un bulletin était déjà calculé, l'écran indique la campagne à recalculer.
- **Fiche salarié** : onglets Fiche / Personnes à charge / Rubriques fixes / Historique et dossier ; « Accès espace salarié » détecte un accès existant (badge + Réinitialiser) au lieu de provoquer une erreur ; changement d'affectation = date d'effet + motif → **historique des mutations** (service, section, emploi, catégorie, site, contrat, salaire).
- **Tableau de bord → Statistiques** : effectifs (sexe, tranches d'âge, ancienneté, contrats, services, sections, emplois, catégories, absences), masse salariale réalisée (évolution mensuelle, trimestres, décomposition, par service/section/emploi/catégorie/nature, heures sup., prêts), prévisionnel annuel. Graphiques Chart.js (ligne, barres, secteurs, anneau).
- **Personnel → Augmentations** : augmentation en masse (% ou montant fixe), aperçu avant application, lots annulables.
- **Paie → Simulation de bulletin** : calcul hypothétique, rien n'est enregistré.
- **Rapports** : liste du personnel, situation de famille, journaux (présences, congés, rubriques, prêts), bulletins à contrôler, cumuls annuels par salarié.
- **Logo** : déposer `backend/app/assets/logo.png` (ou variable `LOGO_PATH`) ; il apparaît sur les bulletins et les lettres. Sans fichier, rien ne change.

## Base de données
`schema.sql` (section 11) puis `params.sql` : idempotents, à rejouer sans risque.

## Installation
1. Sauvegarde : `pg_dump`. 2. Extraire le tar : `tar xzf patch.tar.gz --strip-components=1`. 3. `psql -f backend/scripts/schema.sql` puis `psql -f backend/scripts/params.sql`. 4. `cd frontend && npm install` (ajoute chart.js). 5. Relancer le backend, se reconnecter.
