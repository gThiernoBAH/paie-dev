# Guide de test

Avec le jeu de démonstration (`scripts.demo_data`) : 12 salariés fictifs, 4 journaliers avec 75 jours de pointage en janvier 2026, 1 prêt, 1 demande de congé,
3 campagnes de janvier 2026 déjà préparées. Comptes de test affichés à la fin du script (mot de passe temporaire à changer à la première connexion) :
`gestion` (gestionnaire de paie), `direction`, `000054` (salarié). L'administrateur est `admin`.

## 1. Le cas de référence (bulletin réel)
1. Connexion `admin` → **Campagnes de paie** → **Paie 01/2026** → onglet *Présences* : TRAORE Mamadou (000054) a déjà 3 jours et 4 h d'absence, 3 h sup.
2. **Calculer**. Onglet *Bulletins* : le net de 000054 doit être **205 014 FCFA** (CNPS 14 058, ITS 0). Cliquer **Voir**, puis l'icône PDF : comparer avec le bulletin papier.
3. **Valider** → refusé : « Paramètres critiques à confirmer ». C'est voulu : *Paramétrage* → *Voir ceux à confirmer*, vérifier chaque taux, puis confirmer (ou, pour un essai rapide, relancer la démo avec `--confirmer-parametres`).
4. **Valider** de nouveau → les bulletins sont figés. Essayer **Calculer** : refusé. **Rouvrir** (administrateur, motif obligatoire) les ramène en brouillon.

## 2. Journaliers (quinzaines)
1. *Pointages* : consulter les pointages importés ; *Calcul des présences* pour un matricule `000101`.
2. Campagne **Paie 01/2026 n°2** (1–15 janvier) → **Présences depuis les pointages** → corriger au besoin → **Calculer**. Comparer HT, gratification, congés avec le legacy.
3. Importer un autre fichier (`matricule;date;entree;sortie`) dans *Pointages → Import*.

## 3. Cas spéciaux
- **Prêt** : *Prêts et avances* → le prêt de 000056 prélève 20 000 F par mois à partir de février 2026. Créer la campagne de février, *Ajouter les salariés*, *Calculer* : la rubrique PRE apparaît dans *Rubriques variables*.
- **Congé** : *Congés* → approuver la demande de 000055 ; contrôler le solde dans l'onglet *Soldes*.
- **Solde de tout compte** : *Campagnes de paie* → *Solde de tout compte* → matricule, date, motif « Licenciement », *Aperçu* puis *Créer*.
- **Prime pour tous** : dans une campagne, *Rubriques variables* → « Pour tous » (ex. GRT = 10 % du salaire).

## 4. Sorties
Après validation : **Préparer les virements** (contrôler les exclus, exporter Excel/CSV, **Lancer**), **Journal comptable**, *Déclarations* (CNPS, ITS, FDFP, DISA), **Envoyer par e-mail** (nécessite la config SMTP).

## 5. Espace salarié (téléphone)
Se connecter avec `000054` : changer le mot de passe, consulter le bulletin de janvier, demander un congé. Sur mobile : menu du navigateur → « Installer l'application ».
Vérifier qu'un salarié ne peut pas voir `/salaries`, ni les bulletins d'un collègue.

## 6. Sécurité à tester
- Compte `direction` : voit les rapports agrégés, pas le salaire des salariés, pas le livre de paie.
- *Administration → Audit* : connexions, calculs, validations, exports de RIB, consultations CNPS, tout est tracé.
- Après 5 mauvais mots de passe, le compte est verrouillé 15 minutes.
