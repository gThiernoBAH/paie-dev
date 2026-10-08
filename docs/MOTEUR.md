# Moteur de paie — règles appliquées

Code : `backend/app/moteur/`. Fonctions pures ; les valeurs légales viennent des paramètres datés (écran Paramétrage).
Tests de référence : `backend/tests/test_moteur.py` (bulletins réels SIVOP).

## Chaîne de calcul d'un bulletin
1. **Gains imposables (GI)** puis **retenues imposables (RI)** → `TIG`, `TIR`.
2. **Total imposable `TI`** = TIG − TIR, arrondi au franc le plus proche.
3. **CNPS salarié** = 6,3 % × min(TI, plafond 3 375 000), selon le mode d'arrondi (troncature, constatée sur les bulletins).
4. **ITS** = barème progressif par tranches mensuelles (0 / 16 / 21 / 24 / 28 / 32 %) − réduction pour charges de famille
   (5 500 F par demi-part au-delà de 1 part, max 44 000 F). Arrondi au franc le plus proche (mensuels).
5. **Net non imposable `TNI`** = gains non imposables − retenues non imposables (CMU, acomptes, assurances…).
6. **Net à payer** = TI − (CNPS + ITS) + TNI.

## Mensuels
- Salaire catégoriel (`JT`), sursalaire (`SS`), ancienneté (`ANC` = taux × salaire catégoriel, 1 %/année révolue dès 25 mois, max 25 %).
- Taux horaire = montant mensuel / 173,33 (arrondi au centime), catégoriel et sursalaire séparés puis additionnés.
- Heures supplémentaires `HS1..HS4` = heures × taux horaire total × (1 + majoration 15/50/75/100 %).
- Absences non payées : `ABS` (heures) et `JA` (jours × 8 h), au taux horaire total, retenues imposables.
- Transport : part jusqu'à 30 000 F non imposable (`TSP`), excédent imposable (`TSI`), proratisé sur les jours de présence / 30.
- CMU salarié : 500 F × personnes couvertes (retenue non imposable).

## Journaliers (payés par quinzaine, calcul par bulletin)
- `HT` = heures × taux horaire (75 000 / 173,33 = 432,70).
- `GRA` gratification = 6,25 % × (HT + HS au taux simple) ; `CON` congés = 10,154 % × (HT + HS majorées + GRA).
- Transport 1 000 F par jour de présence (non imposable). Prime de précarité : 2 868 F par mois complet (non imposable), saisie en rubrique.
- ITS « mensualisé » : revenu ramené à un mois (× 30 / jours), taxé au barème, puis ramené aux jours payés ; arrondi par troncature.

## Écarts connus (à lever avec les vrais bulletins)
- **Q30** : l'ITS des journaliers d'août (1 455 F et 1 290 F) n'est pas reproduit ; janvier l'est exactement.
- **Q36** : heures de nuit sur jours ordinaires.
- Le legacy arrondit certaines lignes de quelques centimes autrement ; les comparaisons de lignes tolèrent 0,10 F, les totaux sont exacts.
- Parts fiscales : règle proposée dans `services/salaries.py` (à confirmer), toujours modifiable sur la fiche.
