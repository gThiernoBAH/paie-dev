# Nouveautés de l'interface (refonte d'octobre 2026)

## Aspect et navigation
- Palette « Ivoire » (crème, vert profond, orange) identique sur PC et mobile ; tout se règle dans `frontend/src/style.css` (variables `--color-*`, `--nav-*`).
- Barre latérale **pliable** : les icônes restent visibles quand elle est réduite ; survoler une icône ouvre la liste des écrans du groupe. L'état (plié / déplié) est mémorisé par navigateur.
- 5 groupes : **Pilotage**, **Personnel**, **Paie**, **Règlements**, **Configuration**. Le menu est défini en un seul endroit : `frontend/src/navigation.js`.
- Fil d'Ariane et menu utilisateur (changer son mot de passe, se déconnecter) dans la barre du haut.

## Composants communs
- `DataTable` : recherche, tri par colonne, pagination (10/25/50/100) sur **tous** les tableaux. Les listes volumineuses (salariés, journal d'audit) trient et paginent côté serveur.
- Fenêtres de confirmation et de saisie intégrées (plus aucune fenêtre du navigateur) : `useConfirm()` (`confirm`, `saisir`).
- Infobulles : tout élément portant `data-hint="…"` ; les boutons à icône seule utilisent `BoutonIcone` (infobulle et libellé accessible obligatoires).
- Copie dans le presse-papiers qui fonctionne aussi en `http://` (sans HTTPS).

## Mobile = consultation
- Sur téléphone, tout est en **lecture seule**, y compris pour l'administrateur ; l'**administration n'est pas accessible**.
- Appliqué aussi par le serveur : le jeton porte le canal « mobile » (déclaré par l'interface, ou détecté par le navigateur). Toute écriture est refusée (403), sauf pour le salarié : ses propres demandes de congé et son mot de passe.
- Ce n'est pas une barrière contre un attaquant déterminé (le canal vient du client) : pour une interdiction stricte, ajouter une restriction réseau au déploiement.

## Corrections
- Comptes : à la saisie d'un matricule connu, nom, prénom, e-mail et téléphone sont repris de la fiche salarié et verrouillés (le serveur impose aussi ces valeurs).
- Congés et absences : filtre par type (congés annuels, permissions exceptionnelles, maladies…), boutons « Approuver » / « Refuser » explicites.
- Référentiels : aide sous chaque onglet, « Renommer » sur les rubriques de paie.
- Prêts, campagnes, pointages : formulaires avec libellés visibles (année, mois…).
- Espace salarié : « Mes demandes » filtrables et paginées, bouton « Annuler » explicite.


## Nouveaux modules
- **Dossier disciplinaire** (Personnel) : avertissements, blâmes, mises à pied, avec lettre PDF et annulation tracée (jamais de suppression). Une **mise à pied** retire de la paie du mois ses **jours ouvrés** (lundi–vendredi hors jours fériés) via la ligne « Absences (jours) » ; l'écran des présences de la campagne l'indique. Les **notes de service** (tout le personnel ou un service) ont leur PDF. Droit : `gerer_discipline` (rôle paie ; l'admin l'a d'office).
- **Gratifications** (Paie) : choisir une campagne non validée, proposer un montant fixe ou un % du salaire (par service si besoin), ajuster ligne par ligne, enregistrer. Relancer ensuite le calcul de la campagne.
- **Lettres de virement** : dans Virements, bouton « Lettres aux banques » = une lettre PDF par banque avec la liste des bénéficiaires (RIB en clair, accès tracé).

## Mise à jour de la base (obligatoire)
Rejouer, sans risque pour les données existantes :
```
psql <DATABASE_URL> -f backend/scripts/schema.sql
psql <DATABASE_URL> -f backend/scripts/params.sql
```
Nouvelles tables : `mesures_disciplinaires`, `notes_service`. Nouveaux paramètres (Paramétrage > Entreprise, « à confirmer ») : n° de compte débiteur, signataire, ville des lettres.

## À valider
- Textes des lettres disciplinaires et procédure (convocation, délais, entretien préalable) : modèles à faire valider par le juridique.
- Mise à pied décomptée en jours ouvrés (lun–ven) : à confirmer si votre règle est en jours calendaires ou ouvrables (samedi inclus).
- Mise à pied non appliquée aux bulletins journaliers (pas de salaire sans jour travaillé).
