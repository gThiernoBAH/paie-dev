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

DO $$ BEGIN RAISE NOTICE 'Schéma SIVOP Paie à jour'; END; $$;
