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

DO $$ BEGIN RAISE NOTICE 'Schéma SIVOP Paie à jour'; END; $$;
