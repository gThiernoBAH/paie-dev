-- =============================================================================
-- SIVOP PAIE -- schema.sql
-- Schéma de la base PostgreSQL (une seule base, mono-société, tous exercices).
-- Décrit l'état COURANT du schéma, rejouable sans risque (IF NOT EXISTS / OR REPLACE).
-- Les évolutions ultérieures passent aussi par backend/migrations/NNN_*.sql (décision D2).
-- Les données de référence (paramètres légaux, rubriques...) sont dans params.sql.
-- Conventions : tables au pluriel français en snake_case, montants en numeric, dates en timestamptz.
-- =============================================================================

DO $$ BEGIN RAISE NOTICE 'Création du schéma SIVOP Paie (schema.sql)'; END; $$;

-- =============================================================
-- 0. SUIVI DES MIGRATIONS
-- =============================================================
CREATE TABLE IF NOT EXISTS migrations_appliquees (
    nom VARCHAR(120) PRIMARY KEY,
    appliquee_le TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================
-- 1. AUTHENTIFICATION ET DROITS
-- =============================================================

-- Un compte = une personne. `identifiant` est le matricule pour un salarié (6 chiffres, zéros
-- initiaux conservés : '045700'), ou un nom court pour un compte d'administration ('admin').
CREATE TABLE IF NOT EXISTS utilisateurs (
    id SERIAL PRIMARY KEY,
    identifiant VARCHAR(20) NOT NULL UNIQUE,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100),
    email VARCHAR(150),
    telephone VARCHAR(30),
    mot_de_passe_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'salarie'
        CHECK (role IN ('admin', 'paie', 'direction', 'salarie')),
    est_actif BOOLEAN NOT NULL DEFAULT TRUE,
    doit_changer_mot_de_passe BOOLEAN NOT NULL DEFAULT TRUE,
    derniere_connexion TIMESTAMPTZ,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modifie_le TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_utilisateurs_email ON utilisateurs (LOWER(email)) WHERE email IS NOT NULL;

-- Liste blanche : la présence d'une ligne accorde la permission (un administrateur les a toutes).
CREATE TABLE IF NOT EXISTS permissions_utilisateurs (
    utilisateur_id INTEGER NOT NULL REFERENCES utilisateurs(id) ON DELETE CASCADE,
    permission VARCHAR(50) NOT NULL,
    accordee_le TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (utilisateur_id, permission)
);

-- =============================================================
-- 2. JOURNAL D'AUDIT (non modifiable)
-- =============================================================
-- Qui a fait quoi, quand, depuis où. Les lignes ne se modifient ni ne se suppriment (trigger
-- ci-dessous) : c'est ce qui rend le journal opposable. `acteur_identifiant` est recopié pour
-- que la trace reste lisible même si le compte est désactivé plus tard.
CREATE TABLE IF NOT EXISTS journal_audit (
    id BIGSERIAL PRIMARY KEY,
    horodatage TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    acteur_id INTEGER REFERENCES utilisateurs(id),
    acteur_identifiant VARCHAR(20),
    action VARCHAR(60) NOT NULL,
    cible_type VARCHAR(40),
    cible_id VARCHAR(40),
    detail JSONB,
    adresse_ip VARCHAR(45)
);
CREATE INDEX IF NOT EXISTS ix_journal_audit_horodatage ON journal_audit (horodatage DESC);
CREATE INDEX IF NOT EXISTS ix_journal_audit_action ON journal_audit (action);
CREATE INDEX IF NOT EXISTS ix_journal_audit_acteur ON journal_audit (acteur_identifiant);

CREATE OR REPLACE FUNCTION journal_audit_interdit_modification() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'journal_audit est en ajout seul : % interdit', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_journal_audit_immuable ON journal_audit;
CREATE TRIGGER trg_journal_audit_immuable
    BEFORE UPDATE OR DELETE ON journal_audit
    FOR EACH ROW EXECUTE FUNCTION journal_audit_interdit_modification();

-- Remise à zéro volontaire (tests, bases de développement) : seule voie autorisée, via TRUNCATE.

-- =============================================================
-- 3. PARAMÉTRAGE (lot 1)
-- =============================================================
-- Un paramètre = une règle ou une valeur modifiable par l'administrateur depuis l'application
-- (taux, plafonds, barèmes, horaires...). La DÉFINITION (libellé, type, bornes) est ici ; les
-- VALEURS sont datées dans valeurs_parametres : on ajoute une valeur « à partir du ... », on n'écrase
-- jamais l'historique. Le moteur de paie lit la valeur en vigueur à la date de la période payée.
--   type_valeur : entier, decimal, montant (FCFA), pourcentage (6.3 = 6,3 %), texte, booleen,
--                 heure (HH:MM), bareme (liste de tranches en JSON).
--   critique    : un paramètre critique « à confirmer » bloquera la validation des bulletins.
CREATE TABLE IF NOT EXISTS parametres (
    cle VARCHAR(60) PRIMARY KEY,
    categorie VARCHAR(30) NOT NULL,
    libelle VARCHAR(150) NOT NULL,
    description TEXT,
    type_valeur VARCHAR(12) NOT NULL
        CHECK (type_valeur IN ('entier', 'decimal', 'montant', 'pourcentage', 'texte', 'booleen', 'heure', 'bareme')),
    unite VARCHAR(20),
    valeur_min NUMERIC,
    valeur_max NUMERIC,
    choix VARCHAR(200),                       -- texte à choix restreint, séparé par des virgules
    critique BOOLEAN NOT NULL DEFAULT FALSE,
    ordre INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_parametres_categorie ON parametres (categorie, ordre);

-- Valeur datée. statut « a_confirmer » = valeur initiale ou provisoire, à vérifier par un responsable.
CREATE TABLE IF NOT EXISTS valeurs_parametres (
    id SERIAL PRIMARY KEY,
    parametre_cle VARCHAR(60) NOT NULL REFERENCES parametres(cle) ON DELETE CASCADE,
    valeur TEXT NOT NULL,
    date_effet DATE NOT NULL,
    statut VARCHAR(12) NOT NULL DEFAULT 'a_confirmer' CHECK (statut IN ('confirme', 'a_confirmer')),
    source VARCHAR(200),
    commentaire TEXT,
    cree_par VARCHAR(20),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirme_par VARCHAR(20),
    confirme_le TIMESTAMPTZ,
    UNIQUE (parametre_cle, date_effet)
);
CREATE INDEX IF NOT EXISTS ix_valeurs_parametres_cle ON valeurs_parametres (parametre_cle, date_effet DESC);

-- =============================================================
-- 4. RÉFÉRENTIELS ET SALARIÉS (lot 2)
-- =============================================================
-- Listes paramétrables par l'administrateur (services, sections, emplois, catégories, sites, banques,
-- types de contrat). Une seule table : ajouter un type de liste ne demande aucune migration.
-- `extra` porte les informations propres à un type (ex. code banque, ou salaire de référence d'une catégorie).
-- On ne supprime pas une ligne utilisée : on la désactive (est_actif = FALSE).
CREATE TABLE IF NOT EXISTS referentiels (
    id SERIAL PRIMARY KEY,
    type_ref VARCHAR(30) NOT NULL
        CHECK (type_ref IN ('service', 'section', 'emploi', 'categorie', 'site', 'banque', 'type_contrat')),
    code VARCHAR(20) NOT NULL,
    libelle VARCHAR(150) NOT NULL,
    extra JSONB,
    est_actif BOOLEAN NOT NULL DEFAULT TRUE,
    ordre INTEGER NOT NULL DEFAULT 0,
    UNIQUE (type_ref, code)
);

-- Un salarié. `matricule` = identifiant de connexion de l'espace salarié (6 chiffres, zéros initiaux conservés).
-- RIB et n° CNPS sont CHIFFRÉS (préfixe enc1:, cf. core/crypto.py) : jamais en clair en base.
-- Le salaire n'est pas ici : il vit dans evolutions_salaire (historique daté).
CREATE TABLE IF NOT EXISTS salaries (
    id SERIAL PRIMARY KEY,
    matricule CHAR(6) NOT NULL UNIQUE CHECK (matricule ~ '^[0-9]{6}$'),
    nom VARCHAR(100) NOT NULL,
    prenoms VARCHAR(150),
    sexe CHAR(1) CHECK (sexe IN ('M', 'F')),
    date_naissance DATE,
    lieu_naissance VARCHAR(100),
    nationalite VARCHAR(60) DEFAULT 'Ivoirienne',
    situation_matrimoniale VARCHAR(15) NOT NULL DEFAULT 'celibataire'
        CHECK (situation_matrimoniale IN ('celibataire', 'marie', 'divorce', 'veuf')),
    nombre_enfants INTEGER NOT NULL DEFAULT 0 CHECK (nombre_enfants BETWEEN 0 AND 30),
    nombre_parts NUMERIC(3,1) NOT NULL DEFAULT 1 CHECK (nombre_parts BETWEEN 1 AND 5),
    nombre_personnes_cmu INTEGER NOT NULL DEFAULT 1 CHECK (nombre_personnes_cmu BETWEEN 0 AND 30),
    telephone VARCHAR(30),
    email VARCHAR(150),
    adresse VARCHAR(200),
    ville VARCHAR(80),
    date_embauche DATE,
    date_sortie DATE,
    motif_sortie VARCHAR(40),
    type_contrat_id INTEGER REFERENCES referentiels(id),
    service_id INTEGER REFERENCES referentiels(id),
    section_id INTEGER REFERENCES referentiels(id),
    emploi_id INTEGER REFERENCES referentiels(id),
    categorie_id INTEGER REFERENCES referentiels(id),
    site_id INTEGER REFERENCES referentiels(id),
    type_remuneration VARCHAR(10) NOT NULL DEFAULT 'mensuel' CHECK (type_remuneration IN ('mensuel', 'journalier')),
    eligible_heures_sup BOOLEAN NOT NULL DEFAULT TRUE,
    mode_paiement VARCHAR(10) NOT NULL DEFAULT 'virement' CHECK (mode_paiement IN ('virement', 'especes', 'cheque')),
    banque_id INTEGER REFERENCES referentiels(id),
    rib_chiffre TEXT,
    numero_cnps_chiffre TEXT,
    indemnite_transport NUMERIC(14,2) CHECK (indemnite_transport IS NULL OR indemnite_transport >= 0),  -- NULL = valeur du paramètre transport_mensuel
    est_actif BOOLEAN NOT NULL DEFAULT TRUE,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modifie_le TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (date_sortie IS NULL OR date_embauche IS NULL OR date_sortie >= date_embauche)
);
CREATE INDEX IF NOT EXISTS ix_salaries_nom ON salaries (LOWER(nom));
CREATE INDEX IF NOT EXISTS ix_salaries_service ON salaries (service_id);
CREATE INDEX IF NOT EXISTS ix_salaries_actif ON salaries (est_actif);

-- Historique daté du salaire de base (mensuel, ou taux journalier pour un journalier).
CREATE TABLE IF NOT EXISTS evolutions_salaire (
    id SERIAL PRIMARY KEY,
    salarie_id INTEGER NOT NULL REFERENCES salaries(id) ON DELETE CASCADE,
    date_effet DATE NOT NULL,
    montant NUMERIC(14,2) NOT NULL CHECK (montant >= 0),   -- salaire catégoriel (base de l'ancienneté)
    sursalaire NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (sursalaire >= 0),
    motif VARCHAR(200),
    cree_par VARCHAR(20),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (salarie_id, date_effet)
);

-- =============================================================
-- 5. POINTAGES, RUBRIQUES (lot 4)
-- =============================================================
-- Jours fériés (fixes et mobiles) : majorent les heures travaillées (HS3 de jour, HS4 de nuit).
-- Les fêtes religieuses mobiles sont saisies par l'administrateur chaque année.
CREATE TABLE IF NOT EXISTS jours_feries (
    jour DATE PRIMARY KEY,
    libelle VARCHAR(100) NOT NULL
);

-- Un fichier de pointages importé (traçabilité : qui, quand, combien de lignes, lesquelles rejetées).
CREATE TABLE IF NOT EXISTS imports_pointages (
    id SERIAL PRIMARY KEY,
    nom_fichier VARCHAR(200),
    importe_par VARCHAR(20),
    importe_le TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    nb_lignes INTEGER NOT NULL DEFAULT 0,
    nb_jours INTEGER NOT NULL DEFAULT 0,
    nb_rejets INTEGER NOT NULL DEFAULT 0,
    rejets JSONB
);

-- Une ligne par salarié et par jour : première entrée et dernière sortie.
CREATE TABLE IF NOT EXISTS pointages (
    id BIGSERIAL PRIMARY KEY,
    salarie_id INTEGER NOT NULL REFERENCES salaries(id),
    jour DATE NOT NULL,
    heure_entree TIME,
    heure_sortie TIME,
    source VARCHAR(10) NOT NULL DEFAULT 'manuel' CHECK (source IN ('import', 'manuel')),
    import_id INTEGER REFERENCES imports_pointages(id) ON DELETE SET NULL,
    commentaire VARCHAR(200),
    cree_par VARCHAR(20),
    modifie_le TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (salarie_id, jour)
);
CREATE INDEX IF NOT EXISTS ix_pointages_jour ON pointages (jour);

-- Catalogue des rubriques variables saisissables sur un bulletin (primes, retenues, acomptes...).
--   type : GI gain imposable, GN gain non imposable, RI retenue imposable, RN retenue non imposable.
CREATE TABLE IF NOT EXISTS rubriques (
    code VARCHAR(6) PRIMARY KEY,
    libelle VARCHAR(100) NOT NULL,
    type VARCHAR(2) NOT NULL CHECK (type IN ('GI', 'GN', 'RI', 'RN')),
    montant_defaut NUMERIC(14,2),
    est_actif BOOLEAN NOT NULL DEFAULT TRUE
);

-- =============================================================
-- 6. CAMPAGNES DE PAIE ET BULLETINS (lot 5)
-- =============================================================
-- Une campagne = une période payée pour un groupe de salariés : le mois pour les mensuels, une
-- quinzaine (ou un autre découpage) pour les journaliers -- plusieurs campagnes par mois sont possibles
-- (`numero` = NBUL du legacy). Cycle : ouverte -> calculee -> validee -> cloturee.
CREATE TABLE IF NOT EXISTS campagnes (
    id SERIAL PRIMARY KEY,
    libelle VARCHAR(100) NOT NULL,
    type_campagne VARCHAR(15) NOT NULL DEFAULT 'mensuelle'
        CHECK (type_campagne IN ('mensuelle', 'journaliere', 'solde', 'exceptionnelle')),
    nature_bulletin VARCHAR(10) NOT NULL DEFAULT 'mensuel' CHECK (nature_bulletin IN ('mensuel', 'journalier')),
    annee INTEGER NOT NULL CHECK (annee BETWEEN 2000 AND 2100),
    mois INTEGER NOT NULL CHECK (mois BETWEEN 1 AND 12),
    numero INTEGER NOT NULL DEFAULT 1 CHECK (numero >= 1),
    debut DATE NOT NULL,
    fin DATE NOT NULL,
    date_paie DATE,
    statut VARCHAR(10) NOT NULL DEFAULT 'ouverte' CHECK (statut IN ('ouverte', 'calculee', 'validee', 'cloturee')),
    cree_par VARCHAR(20),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valide_par VARCHAR(20),
    valide_le TIMESTAMPTZ,
    cloture_le TIMESTAMPTZ,
    CHECK (fin >= debut),
    UNIQUE (annee, mois, numero)
);

-- Les éléments de présence qui alimentent le calcul d'un salarié dans une campagne. La présence de la ligne
-- vaut appartenance du salarié à la campagne.
CREATE TABLE IF NOT EXISTS presences_periode (
    campagne_id INTEGER NOT NULL REFERENCES campagnes(id) ON DELETE CASCADE,
    salarie_id INTEGER NOT NULL REFERENCES salaries(id),
    jours_payes NUMERIC(5,1) NOT NULL DEFAULT 30,
    jours_presence NUMERIC(5,1) NOT NULL DEFAULT 0,
    heures_travaillees NUMERIC(7,2) NOT NULL DEFAULT 0,
    hs1 NUMERIC(7,2) NOT NULL DEFAULT 0,
    hs2 NUMERIC(7,2) NOT NULL DEFAULT 0,
    hs3 NUMERIC(7,2) NOT NULL DEFAULT 0,
    hs4 NUMERIC(7,2) NOT NULL DEFAULT 0,
    heures_absence NUMERIC(7,2) NOT NULL DEFAULT 0,
    jours_absence_ja NUMERIC(5,1) NOT NULL DEFAULT 0,
    source VARCHAR(10) NOT NULL DEFAULT 'manuel' CHECK (source IN ('pointage', 'manuel')),
    modifie_par VARCHAR(20),
    modifie_le TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (campagne_id, salarie_id)
);

-- Rubriques variables d'un salarié pour une campagne (prime, acompte, retenue...).
-- `origine` : manuelle, pret (échéance de prêt), solde (solde de tout compte), conges.
CREATE TABLE IF NOT EXISTS saisies_rubriques (
    id SERIAL PRIMARY KEY,
    campagne_id INTEGER NOT NULL REFERENCES campagnes(id) ON DELETE CASCADE,
    salarie_id INTEGER NOT NULL REFERENCES salaries(id),
    code VARCHAR(6) NOT NULL REFERENCES rubriques(code),
    libelle VARCHAR(100) NOT NULL,
    type VARCHAR(2) NOT NULL CHECK (type IN ('GI', 'GN', 'RI', 'RN')),
    montant NUMERIC(14,2) NOT NULL CHECK (montant >= 0),
    quantite NUMERIC(10,2),
    commentaire VARCHAR(200),
    origine VARCHAR(15) NOT NULL DEFAULT 'manuelle',
    reference_id INTEGER,
    cree_par VARCHAR(20),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_saisies_campagne ON saisies_rubriques (campagne_id, salarie_id);

-- Un bulletin. Il garde de quoi être relu à l'identique des années plus tard : les entrées du calcul,
-- les paramètres légaux utilisés (`parametres`), l'identité du salarié à cette date (`identite`) et les lignes.
-- Une fois « valide », il ne change plus (trigger ci-dessous) ; seul un déverrouillage explicite et tracé
-- de la campagne le permet.
CREATE TABLE IF NOT EXISTS bulletins (
    id SERIAL PRIMARY KEY,
    campagne_id INTEGER NOT NULL REFERENCES campagnes(id),
    salarie_id INTEGER NOT NULL REFERENCES salaries(id),
    statut VARCHAR(10) NOT NULL DEFAULT 'brouillon' CHECK (statut IN ('brouillon', 'valide')),
    identite JSONB NOT NULL,
    entree JSONB NOT NULL,
    parametres JSONB NOT NULL,
    lignes JSONB NOT NULL,
    total_imposable_brut NUMERIC(14,2) NOT NULL,
    total_retenues_imposables NUMERIC(14,2) NOT NULL,
    total_imposable NUMERIC(14,2) NOT NULL,
    cnps NUMERIC(14,2) NOT NULL,
    its NUMERIC(14,2) NOT NULL,
    total_impots NUMERIC(14,2) NOT NULL,
    gains_non_imposables NUMERIC(14,2) NOT NULL,
    retenues_non_imposables NUMERIC(14,2) NOT NULL,
    net_non_imposable NUMERIC(14,2) NOT NULL,
    net_a_payer NUMERIC(14,2) NOT NULL,
    charges_patronales JSONB NOT NULL,
    anomalies JSONB NOT NULL DEFAULT '[]'::jsonb,
    calcule_le TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valide_par VARCHAR(20),
    valide_le TIMESTAMPTZ,
    envoye_le TIMESTAMPTZ,
    lu_le TIMESTAMPTZ,
    UNIQUE (campagne_id, salarie_id)
);
CREATE INDEX IF NOT EXISTS ix_bulletins_salarie ON bulletins (salarie_id);

CREATE OR REPLACE FUNCTION bulletins_valides_immuables() RETURNS trigger AS $$
BEGIN
    IF OLD.statut = 'valide' AND COALESCE(current_setting('paie.deverrouillage', true), '') <> 'on' THEN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'Un bulletin validé ne peut pas être supprimé';
        END IF;
        -- seuls les suivis d'envoi et de lecture peuvent évoluer
        IF NEW.statut <> OLD.statut OR NEW.identite <> OLD.identite OR NEW.entree <> OLD.entree
           OR NEW.parametres <> OLD.parametres OR NEW.lignes <> OLD.lignes OR NEW.net_a_payer <> OLD.net_a_payer
           OR NEW.total_imposable <> OLD.total_imposable OR NEW.cnps <> OLD.cnps OR NEW.its <> OLD.its
           OR NEW.net_non_imposable <> OLD.net_non_imposable OR NEW.campagne_id <> OLD.campagne_id
           OR NEW.salarie_id <> OLD.salarie_id OR NEW.charges_patronales <> OLD.charges_patronales THEN
            RAISE EXCEPTION 'Un bulletin validé ne peut pas être modifié';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_bulletins_immuables ON bulletins;
CREATE TRIGGER trg_bulletins_immuables
    BEFORE UPDATE OR DELETE ON bulletins
    FOR EACH ROW EXECUTE FUNCTION bulletins_valides_immuables();

-- =============================================================
-- 7. Congés, prêts et avances
-- =============================================================
ALTER TABLE salaries ADD COLUMN IF NOT EXISTS solde_conges_initial NUMERIC(6,2) NOT NULL DEFAULT 0;
ALTER TABLE salaries ADD COLUMN IF NOT EXISTS solde_conges_date DATE;   -- date à laquelle le solde initial a été arrêté (reprise)

CREATE TABLE IF NOT EXISTS conges (
    id SERIAL PRIMARY KEY,
    salarie_id INTEGER NOT NULL REFERENCES salaries(id),
    type_conge VARCHAR(15) NOT NULL DEFAULT 'annuel'
        CHECK (type_conge IN ('annuel', 'maladie', 'maternite', 'exceptionnel', 'sans_solde')),
    debut DATE NOT NULL,
    fin DATE NOT NULL,
    jours_ouvrables NUMERIC(5,1) NOT NULL CHECK (jours_ouvrables >= 0),
    statut VARCHAR(10) NOT NULL DEFAULT 'demande' CHECK (statut IN ('demande', 'approuve', 'refuse', 'annule')),
    motif VARCHAR(200),
    decide_par VARCHAR(20),
    decide_le TIMESTAMPTZ,
    cree_par VARCHAR(20),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (fin >= debut)
);
CREATE INDEX IF NOT EXISTS ix_conges_salarie ON conges (salarie_id, debut);

CREATE TABLE IF NOT EXISTS prets (
    id SERIAL PRIMARY KEY,
    salarie_id INTEGER NOT NULL REFERENCES salaries(id),
    type_pret VARCHAR(10) NOT NULL DEFAULT 'pret' CHECK (type_pret IN ('pret', 'avance')),
    libelle VARCHAR(100) NOT NULL,
    montant NUMERIC(14,2) NOT NULL CHECK (montant > 0),
    nombre_echeances INTEGER NOT NULL CHECK (nombre_echeances BETWEEN 1 AND 120),
    statut VARCHAR(10) NOT NULL DEFAULT 'actif' CHECK (statut IN ('actif', 'solde', 'annule')),
    cree_par VARCHAR(20),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_prets_salarie ON prets (salarie_id);

CREATE TABLE IF NOT EXISTS echeances_prets (
    id SERIAL PRIMARY KEY,
    pret_id INTEGER NOT NULL REFERENCES prets(id) ON DELETE CASCADE,
    annee INTEGER NOT NULL,
    mois INTEGER NOT NULL CHECK (mois BETWEEN 1 AND 12),
    montant NUMERIC(14,2) NOT NULL CHECK (montant > 0),
    statut VARCHAR(10) NOT NULL DEFAULT 'prevue' CHECK (statut IN ('prevue', 'prelevee', 'annulee')),
    campagne_id INTEGER REFERENCES campagnes(id) ON DELETE SET NULL,
    UNIQUE (pret_id, annee, mois)
);
CREATE INDEX IF NOT EXISTS ix_echeances_statut ON echeances_prets (statut, annee, mois);

-- =============================================================
-- 8. Virements bancaires
-- =============================================================
-- Un lot = les virements d'une campagne validée. Le RIB (chiffré) est copié sur chaque ordre au moment
-- de la préparation : le fichier de virement reflète exactement ce qui a été contrôlé.
CREATE TABLE IF NOT EXISTS lots_virement (
    id SERIAL PRIMARY KEY,
    campagne_id INTEGER NOT NULL REFERENCES campagnes(id),
    libelle VARCHAR(120) NOT NULL,
    date_valeur DATE,
    statut VARCHAR(10) NOT NULL DEFAULT 'prepare' CHECK (statut IN ('prepare', 'lance', 'annule')),
    nombre_ordres INTEGER NOT NULL DEFAULT 0,
    total NUMERIC(16,2) NOT NULL DEFAULT 0,
    exclus JSONB NOT NULL DEFAULT '[]'::jsonb,       -- salariés non virés et pourquoi (sans RIB, espèces...)
    cree_par VARCHAR(20),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lance_par VARCHAR(20),
    lance_le TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_lots_virement_campagne ON lots_virement (campagne_id);

CREATE TABLE IF NOT EXISTS ordres_virement (
    id SERIAL PRIMARY KEY,
    lot_id INTEGER NOT NULL REFERENCES lots_virement(id) ON DELETE CASCADE,
    salarie_id INTEGER NOT NULL REFERENCES salaries(id),
    bulletin_id INTEGER REFERENCES bulletins(id),
    montant NUMERIC(14,2) NOT NULL CHECK (montant > 0),
    banque VARCHAR(100),
    rib_chiffre TEXT NOT NULL,
    UNIQUE (lot_id, salarie_id)
);

DO $$ BEGIN RAISE NOTICE 'Schéma SIVOP Paie à jour'; END; $$;
