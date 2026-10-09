# Points à confirmer avant la mise en production

L'application ne bloque jamais sur une valeur inconnue : elle prend une valeur initiale marquée **« à confirmer »**. Les paramètres *critiques* non confirmés empêchent seulement la **validation** des bulletins.

## Règles de calcul encore ouvertes
1. **ITS des journaliers (Q30)** : l'ITS des journaliers d'août (1 455 F et 1 290 F sur vos bulletins) n'est pas reproduit ; celui de janvier l'est exactement. Les tests correspondants sont marqués « attendu en échec » pour ne pas masquer le problème. → Il faut un ou deux bulletins journaliers supplémentaires avec le détail.
2. **Heures de nuit sur jours ordinaires (Q36)** : le comportement du legacy n'est pas établi ; la règle appliquée est celle du paramétrage (22 h–6 h).
3. **Formation continue** : 0,6 % ou 1,2 % selon l'effectif / l'année ; à vérifier avec la DGI.
4. **Parts fiscales** : règle de calcul proposée à la création (modifiable sur la fiche) à confirmer.
5. **Indemnité de licenciement** : tranches 30/35/40 % (5 et 10 ans) issues du legacy, base = salaire catégoriel + sursalaire. Le « plafond » du legacy (PLAF_LIC = 50 000) sépare la part non imposable de la part imposable : à confirmer avec votre conseil juridique.
6. **Valorisation des congés payés** : salaire mensuel ÷ 26 × jours (paramétrable).

## Formats externes
- **CNPS / DISA / ITS** : gabarits officiels à comparer (voir `DECLARATIONS.md`).
- **Fichier de virement** : format exact du portail de votre banque.
- **Pointeuse** : le format du fichier est générique (`matricule;date;heure` ou `matricule;date;entree;sortie`) ; à adapter à votre matériel.
- **E-mail** : hôte SMTP, expéditeur, modèle du message.

## À faire ensemble ensuite
- **Lot 12 – reprise des données** : import des salariés, historiques de salaire, soldes de congés, prêts en cours depuis SQL Server (RIB et CNPS chiffrés à l'import).
- **Lot 13 – déploiement** sur le serveur SIVOP : TLS, sauvegardes, supervision, 2FA (non fait).

## Paramètres initialisés « à confirmer »
### Critiques (bloquent la validation tant qu'ils ne sont pas confirmés)

| Paramètre | Valeur initiale | Origine |
|---|---|---|
| Arrondi de l'ITS (journaliers) | troncature | Bulletins réels 2026 (cas de référence) |
| Arrondi des cotisations salariales | troncature | Legacy Delphi (table FIPARA) |
| CNPS retraite – part employeur | 7.7 | Legacy Delphi (table FIPARA) |
| Prestations familiales (maternité incluse) | 5.75 | Legacy Delphi (table FIPARA) |
| Prestations familiales – plafond mensuel | 75000 | Legacy Delphi (table FIPARA) |
| Accident du travail | 4 | Legacy Delphi (table FIPARA) |
| Taxe d'apprentissage | 0.4 | Legacy Delphi (table FIPARA) |
| Formation professionnelle continue | 0.6 | Legacy Delphi (table FIPARA) |
| Journaliers – base de mensualisation de l'ITS | 30 | Bulletins réels 2026 (cas de référence) |

### Non critiques

| Paramètre | Valeur initiale | Origine |
|---|---|---|
| Raison sociale | SIVOP | Valeur initiale |
| N° employeur CNPS | À renseigner | Valeur initiale |
| N° compte contribuable | À renseigner | Valeur initiale |
| Adresse | Abidjan, Côte d'Ivoire | Valeur initiale |
| Début des heures de nuit | 22:00 | Legacy Delphi (table FIPARA) |
| Fin des heures de nuit | 06:00 | Legacy Delphi (table FIPARA) |
| Prime d'ancienneté – seuil | 25 | Legacy Delphi (table FIPARA) |
| Prime d'ancienneté – taux par année | 1 | Legacy Delphi (table FIPARA) |
| Prime d'ancienneté – plafond | 25 | Legacy Delphi (table FIPARA) |
| Congés – jours calendaires par mois | 2.75 | Legacy Delphi (table FIPARA) |
| Allocation de congés | 9.1667 | Legacy Delphi (table FIPARA) |
| Indemnité de licenciement – tranche 1 | 30 | Legacy Delphi (table FIPARA) |
| Indemnité de licenciement – tranche 2 | 35 | Legacy Delphi (table FIPARA) |
| Indemnité de licenciement – tranche 3 | 40 | Legacy Delphi (table FIPARA) |
| Licenciement – fin de tranche 1 | 5 | Legacy Delphi (table FIPARA) |
| Licenciement – fin de tranche 2 | 10 | Legacy Delphi (table FIPARA) |
| Licenciement – plafond (PLAF_LIC) | 50000 | Legacy Delphi (table FIPARA) |
| Pause déduite du temps de présence | 60 | Valeur initiale |
| Seuil de durée pour déduire la pause | 6 | Valeur initiale |
| Jours ouvrés de la semaine | 1,2,3,4,5 | Valeur initiale |
| Proposer les absences détectées | false | Valeur initiale |
| CMU – appliquer aux journaliers | false | Bulletins réels 2026 (cas de référence) |
| Congés – jours de référence du mois | 26 | Pratique courante (jours ouvrables) – à confirmer |
| Code du journal de paie | OD | Plan SYSCOHADA usuel – à valider par le comptable |
| Compte : rémunérations (gains imposables) | 661000 | Plan SYSCOHADA usuel – à valider par le comptable |
| Compte : indemnités et avantages non imposables | 663000 | Plan SYSCOHADA usuel – à valider par le comptable |
| Compte : charges sociales patronales CNPS | 664100 | Plan SYSCOHADA usuel – à valider par le comptable |
| Compte : taxes FDFP (apprentissage, formation) | 664200 | Plan SYSCOHADA usuel – à valider par le comptable |
| Compte : impôt sur traitements et salaires retenu | 447100 | Plan SYSCOHADA usuel – à valider par le comptable |
| Compte : organismes sociaux CNPS | 431100 | Plan SYSCOHADA usuel – à valider par le comptable |
| Compte : FDFP à payer | 447200 | Plan SYSCOHADA usuel – à valider par le comptable |
| Compte : CMU à reverser | 431200 | Plan SYSCOHADA usuel – à valider par le comptable |
| Compte : avances, acomptes et prêts au personnel | 425000 | Plan SYSCOHADA usuel – à valider par le comptable |
| Compte : autres retenues au personnel | 422900 | Plan SYSCOHADA usuel – à valider par le comptable |
| Compte : rémunérations dues au personnel | 422000 | Plan SYSCOHADA usuel – à valider par le comptable |
| Compte : écarts d'arrondi de paie | 658000 | Plan SYSCOHADA usuel – à valider par le comptable |
| Serveur SMTP – hôte | smtp.exemple.ci | Valeur initiale – à renseigner |
| Serveur SMTP – port | 587 | Valeur initiale – à renseigner |
| Serveur SMTP – sécurité | starttls | Valeur initiale – à renseigner |
| Serveur SMTP – identifiant | - | Valeur initiale – à renseigner |
| Adresse d'expédition | paie@sivop.ci | Valeur initiale – à renseigner |
| Nom d'expéditeur | SIVOP – Service Paie | Valeur initiale – à renseigner |
| Objet du message de bulletin | Votre bulletin de paie – {periode} | Valeur initiale – à renseigner |
| Texte du message de bulletin | Bonjour {prenom},\n\nVeuillez trouver ci-joint votre bulleti | Valeur initiale – à renseigner |
| Destinataires de l'alerte virement | - | Valeur initiale – à renseigner |

## Octobre 2026
- **Mode de paiement des congés** (`conges_mode_paiement`) : `maintien_salaire` (par défaut, à confirmer) ou `indemnite_conges` (rubriques CGR/ICP, majoration `conges_majoration_indemnite`). À valider avec le cabinet / la convention collective.
- **Tranches d'âge** : corrigées par rapport au legacy (≤25, 26-35, 36-45, 46+, « Non renseigné »).
- **« Salaire réel / hors salaire »** : volontairement non repris. Un paiement hors bulletin n'est pas déclaré à la CNPS ni à l'ITS (risque de conformité). Les avantages légitimes se déclarent en rubriques (fixes ou variables) ; le coût complet employeur est disponible dans les statistiques.
- **Non réalisés, à confirmer** : grille salariale par catégorie ; mise en page du bulletin paramétrable ; la « clôture annuelle » se limite aux cumuls annuels consultables (rapport) — pas de verrouillage d'année.

## Lot 12
- **Tranches horaires** : heures déduites des captures du legacy, à confirmer (probables régimes d'horaires hebdomadaires ; la tranche 5 ressemble à un mi-temps). Reprise de la tranche de chaque salarié à faire depuis l'ancien logiciel.
- **Base horaire par catégorie** : à importer depuis l'ancien logiciel (écran Grille salariale → Importer).
- **Bulletin** : éléments à afficher ou masquer à valider avec le service de la paie (réglages dans Paramétrage → Bulletin de paie).
- **« Salaire réel / hors salaire »** : non repris (le legacy le calculait comme `salaire réel − (catégoriel + sursalaire)`, hors bulletin). Équivalents légitimes à décider : contrôle « salaire du contrat » / « bulletin », suivi des avantages en nature et remboursements de frais avec plafonds.
