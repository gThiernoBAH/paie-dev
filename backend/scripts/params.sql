-- =============================================================================
-- SIVOP PAIE -- params.sql
-- Données de référence, à jouer APRÈS schema.sql (rejouable : ON CONFLICT DO NOTHING).
-- Le compte administrateur se crée par scripts/create_admin.py (jamais de mot de passe ici).
--
-- LOT 1 : paramètres légaux et de paramétrage, avec leur valeur initiale datée du 2000-01-01.
-- Statut « confirme » = recoupé avec des bulletins réels 2026 ; « a_confirmer » = valeur du legacy
-- ou provisoire. Rien ne bloque : l'administrateur corrige depuis l'écran Paramétrage, et chaque
-- changement est daté, tracé, sans toucher aux bulletins déjà validés.
-- Ce fichier ne remplace JAMAIS une valeur modifiée depuis l'application (ON CONFLICT DO NOTHING).
-- =============================================================================

INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('entreprise_raison_sociale', 'entreprise', 'Raison sociale', 'Nom imprimé sur les bulletins et déclarations.', 'texte', NULL, NULL, NULL, NULL, FALSE, 10)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('entreprise_raison_sociale', 'SIVOP', DATE '2000-01-01', 'a_confirmer', 'Valeur initiale', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('entreprise_numero_cnps', 'entreprise', 'N° employeur CNPS', 'Numéro d''immatriculation de l''employeur à la CNPS.', 'texte', NULL, NULL, NULL, NULL, FALSE, 20)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('entreprise_numero_cnps', 'À renseigner', DATE '2000-01-01', 'a_confirmer', 'Valeur initiale', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('entreprise_numero_contribuable', 'entreprise', 'N° compte contribuable', 'Identifiant fiscal (déclarations ITS).', 'texte', NULL, NULL, NULL, NULL, FALSE, 30)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('entreprise_numero_contribuable', 'À renseigner', DATE '2000-01-01', 'a_confirmer', 'Valeur initiale', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('entreprise_adresse', 'entreprise', 'Adresse', 'Adresse imprimée sur les bulletins.', 'texte', NULL, NULL, NULL, NULL, FALSE, 40)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('entreprise_adresse', 'Abidjan, Côte d''Ivoire', DATE '2000-01-01', 'a_confirmer', 'Valeur initiale', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('smig_mensuel', 'general', 'SMIG mensuel', 'Salaire minimum interprofessionnel garanti.', 'montant', 'FCFA', 0, NULL, NULL, TRUE, 50)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('smig_mensuel', '75000', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('heures_mensuelles', 'general', 'Heures mensuelles légales', 'Base de calcul du taux horaire (40 h/semaine).', 'decimal', 'h', 1, 300, NULL, TRUE, 60)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('heures_mensuelles', '173.33', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('heures_hebdo', 'general', 'Durée hebdomadaire légale', 'Au-delà : heures supplémentaires.', 'decimal', 'h', 1, 60, NULL, TRUE, 70)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('heures_hebdo', '40', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('arrondi_its_mensuel', 'general', 'Arrondi de l''ITS (mensuels)', 'Constaté sur le bulletin de mars 2024 : 156 515,68 imprimé 156 516.', 'texte', NULL, NULL, NULL, 'arrondi,troncature', TRUE, 80)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('arrondi_its_mensuel', 'arrondi', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('arrondi_its_journalier', 'general', 'Arrondi de l''ITS (journaliers)', 'Constaté sur le bulletin de janvier 2026 : 992,96 imprimé 992.', 'texte', NULL, NULL, NULL, 'arrondi,troncature', TRUE, 90)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('arrondi_its_journalier', 'troncature', DATE '2000-01-01', 'a_confirmer', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('mode_arrondi_cotisations', 'general', 'Arrondi des cotisations salariales', 'Le legacy tronque à l''entier (troncature). À confirmer avec la CNPS / le cabinet.', 'texte', NULL, NULL, NULL, 'troncature,arrondi', TRUE, 100)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('mode_arrondi_cotisations', 'troncature', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('cnps_taux_retraite_salarie', 'cnps', 'CNPS retraite – part salarié', 'Cotisation retraite retenue sur le salarié.', 'pourcentage', '%', 0, 100, NULL, TRUE, 110)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('cnps_taux_retraite_salarie', '6.3', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('cnps_taux_retraite_employeur', 'cnps', 'CNPS retraite – part employeur', 'Total retraite 14 % = 6,3 % salarié + 7,7 % employeur.', 'pourcentage', '%', 0, 100, NULL, TRUE, 120)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('cnps_taux_retraite_employeur', '7.7', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('cnps_plafond_retraite', 'cnps', 'CNPS retraite – plafond mensuel', 'Plafond de la base de cotisation retraite.', 'montant', 'FCFA', 0, NULL, NULL, TRUE, 130)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('cnps_plafond_retraite', '3375000', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('cnps_taux_prestations_familiales', 'cnps', 'Prestations familiales (maternité incluse)', 'Part employeur.', 'pourcentage', '%', 0, 100, NULL, TRUE, 140)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('cnps_taux_prestations_familiales', '5.75', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('cnps_plafond_prestations_familiales', 'cnps', 'Prestations familiales – plafond mensuel', 'Plafond de la base de cotisation.', 'montant', 'FCFA', 0, NULL, NULL, TRUE, 150)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('cnps_plafond_prestations_familiales', '75000', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('cnps_taux_accident_travail', 'cnps', 'Accident du travail', 'Taux notifié à l''employeur selon son risque.', 'pourcentage', '%', 0, 100, NULL, TRUE, 160)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('cnps_taux_accident_travail', '4', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('fdfp_taux_taxe_apprentissage', 'fdfp', 'Taxe d''apprentissage', 'Part employeur.', 'pourcentage', '%', 0, 100, NULL, TRUE, 170)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('fdfp_taux_taxe_apprentissage', '0.4', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('fdfp_taux_formation_continue', 'fdfp', 'Formation professionnelle continue', 'Le legacy applique 0,6 % ; une autre valeur (1,2 %) a été évoquée : à confirmer.', 'pourcentage', '%', 0, 100, NULL, TRUE, 180)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('fdfp_taux_formation_continue', '0.6', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('its_bareme_mensuel', 'its', 'Barème ITS mensuel', 'Tranches mensuelles : « jusqu''à » (FCFA) et taux (%). La dernière tranche n''a pas de borne.', 'bareme', 'FCFA / %', NULL, NULL, NULL, TRUE, 190)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('its_bareme_mensuel', '[{"jusqu_a": 75000, "taux": 0}, {"jusqu_a": 240000, "taux": 16}, {"jusqu_a": 800000, "taux": 21}, {"jusqu_a": 2400000, "taux": 24}, {"jusqu_a": 8000000, "taux": 28}, {"jusqu_a": null, "taux": 32}]', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('its_ricf_par_demi_part', 'its', 'Réduction d''impôt pour charges de famille', 'Montant par demi-part.', 'montant', 'FCFA', 0, NULL, NULL, TRUE, 200)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('its_ricf_par_demi_part', '5500', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('its_ricf_maximum', 'its', 'Réduction pour charges de famille – maximum', 'Plafond de la réduction.', 'montant', 'FCFA', 0, NULL, NULL, TRUE, 210)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('its_ricf_maximum', '44000', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('cmu_montant_par_personne', 'cmu', 'CMU – cotisation par personne', 'Retenue mensuelle par personne couverte.', 'montant', 'FCFA', 0, NULL, NULL, TRUE, 220)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('cmu_montant_par_personne', '500', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('hs_taux_tranche1', 'heures_sup', 'HS tranche 1 – majoration', 'Premières heures supplémentaires de la semaine.', 'pourcentage', '%', 0, 300, NULL, TRUE, 230)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('hs_taux_tranche1', '15', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('hs_limite_tranche1', 'heures_sup', 'HS tranche 1 – limite hebdomadaire', 'Heures par semaine jusqu''à laquelle la tranche 1 s''applique.', 'decimal', 'h', 0, 100, NULL, TRUE, 240)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('hs_limite_tranche1', '46', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('hs_taux_tranche2', 'heures_sup', 'HS tranche 2 – majoration', 'Au-delà de la tranche 1.', 'pourcentage', '%', 0, 300, NULL, TRUE, 250)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('hs_taux_tranche2', '50', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('hs_taux_tranche3', 'heures_sup', 'HS tranche 3 – majoration', 'Dimanche et jour férié, de jour.', 'pourcentage', '%', 0, 300, NULL, TRUE, 260)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('hs_taux_tranche3', '75', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('hs_taux_tranche4', 'heures_sup', 'HS tranche 4 – majoration', 'Dimanche et jour férié, de nuit.', 'pourcentage', '%', 0, 300, NULL, TRUE, 270)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('hs_taux_tranche4', '100', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('nuit_debut', 'heures_sup', 'Début des heures de nuit', 'Pour le classement des heures (voir aussi question Q36).', 'heure', NULL, NULL, NULL, NULL, FALSE, 280)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('nuit_debut', '22:00', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('nuit_fin', 'heures_sup', 'Fin des heures de nuit', NULL, 'heure', NULL, NULL, NULL, NULL, FALSE, 290)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('nuit_fin', '06:00', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('anciennete_seuil_mois', 'anciennete', 'Prime d''ancienneté – seuil', 'Ancienneté (en mois) à partir de laquelle la prime démarre : 2 ans et 1 mois = 25.', 'entier', 'mois', 0, 600, NULL, FALSE, 300)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('anciennete_seuil_mois', '25', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('anciennete_taux_par_an', 'anciennete', 'Prime d''ancienneté – taux par année', 'Pourcentage du salaire de base par année d''ancienneté.', 'pourcentage', '%', 0, 100, NULL, FALSE, 310)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('anciennete_taux_par_an', '1', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('anciennete_taux_maximum', 'anciennete', 'Prime d''ancienneté – plafond', 'Taux maximum de la prime.', 'pourcentage', '%', 0, 100, NULL, FALSE, 320)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('anciennete_taux_maximum', '25', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('transport_mensuel', 'indemnites', 'Indemnité de transport mensuelle', 'Non imposable, proratisée jours/30.', 'montant', 'FCFA', 0, NULL, NULL, TRUE, 330)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('transport_mensuel', '30000', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('transport_journalier', 'indemnites', 'Indemnité de transport journalière', 'Journaliers : par jour travaillé.', 'montant', 'FCFA', 0, NULL, NULL, TRUE, 340)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('transport_journalier', '1000', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('transport_base_jours', 'indemnites', 'Base de proratisation du transport', 'Nombre de jours du mois pris comme base.', 'entier', 'jours', 1, 31, NULL, FALSE, 350)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('transport_base_jours', '30', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('conges_jours_ouvrables_par_mois', 'conges', 'Congés – jours ouvrables acquis par mois', '2,2 jours par mois = 26,4 jours par an.', 'decimal', 'jours', 0, 10, NULL, TRUE, 360)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('conges_jours_ouvrables_par_mois', '2.2', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('conges_jours_calendaires_par_mois', 'conges', 'Congés – jours calendaires par mois', NULL, 'decimal', 'jours', 0, 10, NULL, FALSE, 370)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('conges_jours_calendaires_par_mois', '2.75', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('conges_taux_allocation', 'conges', 'Allocation de congés', 'Pourcentage servant à valoriser les congés.', 'pourcentage', '%', 0, 100, NULL, FALSE, 380)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('conges_taux_allocation', '9.1667', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('journalier_taux_conges', 'journaliers', 'Journaliers – indemnité de congés', '= 2,2 × 8 / 173,33 du brut.', 'pourcentage', '%', 0, 100, NULL, TRUE, 390)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('journalier_taux_conges', '10.154', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('journalier_taux_gratification', 'journaliers', 'Journaliers – gratification', 'Sur les gains normaux et les HS au taux simple.', 'pourcentage', '%', 0, 100, NULL, TRUE, 400)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('journalier_taux_gratification', '6.25', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('journalier_prime_precarite_mois', 'journaliers', 'Journaliers – prime de précarité (mois complet)', 'Non imposable, proratisée si mois incomplet.', 'montant', 'FCFA', 0, NULL, NULL, TRUE, 410)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('journalier_prime_precarite_mois', '2868', DATE '2000-01-01', 'confirme', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('journalier_base_mensualisation', 'journaliers', 'Journaliers – base de mensualisation de l''ITS', 'L''ITS d''un journalier est calculé comme pour un mois entier (revenu × base / jours), puis ramené aux jours payés. À confirmer (question Q30).', 'entier', 'jours', 1, 31, NULL, TRUE, 420)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('journalier_base_mensualisation', '30', DATE '2000-01-01', 'a_confirmer', 'Bulletins réels 2026 (cas de référence)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('licenciement_taux_tranche1', 'licenciement', 'Indemnité de licenciement – tranche 1', 'Jusqu''à la 1re limite d''ancienneté.', 'pourcentage', '%', 0, 100, NULL, FALSE, 430)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('licenciement_taux_tranche1', '30', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('licenciement_taux_tranche2', 'licenciement', 'Indemnité de licenciement – tranche 2', NULL, 'pourcentage', '%', 0, 100, NULL, FALSE, 440)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('licenciement_taux_tranche2', '35', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('licenciement_taux_tranche3', 'licenciement', 'Indemnité de licenciement – tranche 3', NULL, 'pourcentage', '%', 0, 100, NULL, FALSE, 450)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('licenciement_taux_tranche3', '40', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('licenciement_limite_tranche1', 'licenciement', 'Licenciement – fin de tranche 1', 'Années d''ancienneté.', 'entier', 'ans', 0, 60, NULL, FALSE, 460)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('licenciement_limite_tranche1', '5', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('licenciement_limite_tranche2', 'licenciement', 'Licenciement – fin de tranche 2', 'Années d''ancienneté.', 'entier', 'ans', 0, 60, NULL, FALSE, 470)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('licenciement_limite_tranche2', '10', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;
INSERT INTO parametres (cle, categorie, libelle, description, type_valeur, unite, valeur_min, valeur_max, choix, critique, ordre)
  VALUES ('licenciement_plafond', 'licenciement', 'Licenciement – plafond (PLAF_LIC)', NULL, 'montant', 'FCFA', 0, NULL, NULL, FALSE, 480)
  ON CONFLICT (cle) DO NOTHING;
INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par)
  VALUES ('licenciement_plafond', '50000', DATE '2000-01-01', 'a_confirmer', 'Legacy Delphi (table FIPARA)', 'système')
  ON CONFLICT (parametre_cle, date_effet) DO NOTHING;

-- LOT 2 : référentiels initiaux (modifiables dans l'application ; jamais écrasés)
INSERT INTO referentiels (type_ref, code, libelle, ordre) VALUES ('type_contrat', 'CDI', 'Contrat à durée indéterminée', 10) ON CONFLICT (type_ref, code) DO NOTHING;
INSERT INTO referentiels (type_ref, code, libelle, ordre) VALUES ('type_contrat', 'CDD', 'Contrat à durée déterminée', 20) ON CONFLICT (type_ref, code) DO NOTHING;
INSERT INTO referentiels (type_ref, code, libelle, ordre) VALUES ('type_contrat', 'JOUR', 'Journalier', 30) ON CONFLICT (type_ref, code) DO NOTHING;
INSERT INTO referentiels (type_ref, code, libelle, ordre) VALUES ('type_contrat', 'STAGE', 'Stagiaire', 40) ON CONFLICT (type_ref, code) DO NOTHING;
INSERT INTO referentiels (type_ref, code, libelle, ordre) VALUES ('type_contrat', 'CONS', 'Consultant', 50) ON CONFLICT (type_ref, code) DO NOTHING;
INSERT INTO referentiels (type_ref, code, libelle, ordre) VALUES ('banque', 'SGBCI', 'Société Générale Côte d''Ivoire', 10) ON CONFLICT (type_ref, code) DO NOTHING;
INSERT INTO referentiels (type_ref, code, libelle, ordre) VALUES ('banque', 'SIB', 'Société Ivoirienne de Banque', 20) ON CONFLICT (type_ref, code) DO NOTHING;
INSERT INTO referentiels (type_ref, code, libelle, ordre) VALUES ('banque', 'BICICI', 'BICICI', 30) ON CONFLICT (type_ref, code) DO NOTHING;
INSERT INTO referentiels (type_ref, code, libelle, ordre) VALUES ('banque', 'ECOBANK', 'Ecobank Côte d''Ivoire', 40) ON CONFLICT (type_ref, code) DO NOTHING;
INSERT INTO referentiels (type_ref, code, libelle, ordre) VALUES ('banque', 'NSIA', 'NSIA Banque', 50) ON CONFLICT (type_ref, code) DO NOTHING;
INSERT INTO referentiels (type_ref, code, libelle, ordre) VALUES ('banque', 'BOA', 'Bank of Africa CI', 60) ON CONFLICT (type_ref, code) DO NOTHING;
INSERT INTO referentiels (type_ref, code, libelle, ordre) VALUES ('banque', 'ORABANK', 'Orabank', 70) ON CONFLICT (type_ref, code) DO NOTHING;
INSERT INTO referentiels (type_ref, code, libelle, ordre) VALUES ('banque', 'BACI', 'Banque Atlantique CI', 80) ON CONFLICT (type_ref, code) DO NOTHING;
INSERT INTO referentiels (type_ref, code, libelle, ordre) VALUES ('banque', 'CORIS', 'Coris Bank International', 90) ON CONFLICT (type_ref, code) DO NOTHING;
INSERT INTO referentiels (type_ref, code, libelle, ordre) VALUES ('banque', 'UBA', 'United Bank for Africa CI', 100) ON CONFLICT (type_ref, code) DO NOTHING;
INSERT INTO referentiels (type_ref, code, libelle, ordre) VALUES ('banque', 'BNI', 'Banque Nationale d''Investissement', 110) ON CONFLICT (type_ref, code) DO NOTHING;
INSERT INTO referentiels (type_ref, code, libelle, ordre) VALUES ('banque', 'AUTRE', 'Autre banque', 120) ON CONFLICT (type_ref, code) DO NOTHING;
