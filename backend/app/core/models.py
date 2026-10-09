from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Time
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class Utilisateur(Base):
    __tablename__ = "utilisateurs"

    id = Column(Integer, primary_key=True)
    identifiant = Column(String(20), unique=True, nullable=False)
    nom = Column(String(100), nullable=False)
    prenom = Column(String(100))
    email = Column(String(150))
    telephone = Column(String(30))
    mot_de_passe_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="salarie")
    est_actif = Column(Boolean, nullable=False, default=True)
    doit_changer_mot_de_passe = Column(Boolean, nullable=False, default=True)
    derniere_connexion = Column(DateTime(timezone=True))
    cree_le = Column(DateTime(timezone=True), server_default=func.now())
    modifie_le = Column(DateTime(timezone=True), server_default=func.now())

    permissions = relationship(
        "PermissionUtilisateur", cascade="all, delete-orphan", lazy="selectin", back_populates="utilisateur"
    )

    @property
    def cles_permissions(self) -> list[str]:
        return sorted(p.permission for p in self.permissions)


class PermissionUtilisateur(Base):
    __tablename__ = "permissions_utilisateurs"

    utilisateur_id = Column(Integer, ForeignKey("utilisateurs.id", ondelete="CASCADE"), primary_key=True)
    permission = Column(String(50), primary_key=True)
    accordee_le = Column(DateTime(timezone=True), server_default=func.now())

    utilisateur = relationship("Utilisateur", back_populates="permissions")


class JournalAudit(Base):
    __tablename__ = "journal_audit"

    id = Column(BigInteger, primary_key=True)
    horodatage = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    acteur_id = Column(Integer, ForeignKey("utilisateurs.id"))
    acteur_identifiant = Column(String(20))
    action = Column(String(60), nullable=False)
    cible_type = Column(String(40))
    cible_id = Column(String(40))
    detail = Column(JSONB)
    adresse_ip = Column(String(45))


class Parametre(Base):
    __tablename__ = "parametres"

    cle = Column(String(60), primary_key=True)
    categorie = Column(String(30), nullable=False)
    libelle = Column(String(150), nullable=False)
    description = Column(Text)
    type_valeur = Column(String(12), nullable=False)
    unite = Column(String(20))
    valeur_min = Column(Numeric)
    valeur_max = Column(Numeric)
    choix = Column(String(200))
    critique = Column(Boolean, nullable=False, default=False)
    ordre = Column(Integer, nullable=False, default=0)

    valeurs = relationship(
        "ValeurParametre", cascade="all, delete-orphan", lazy="selectin",
        order_by="ValeurParametre.date_effet.desc()", back_populates="parametre",
    )


class ValeurParametre(Base):
    __tablename__ = "valeurs_parametres"

    id = Column(Integer, primary_key=True)
    parametre_cle = Column(String(60), ForeignKey("parametres.cle", ondelete="CASCADE"), nullable=False)
    valeur = Column(Text, nullable=False)
    date_effet = Column(Date, nullable=False)
    statut = Column(String(12), nullable=False, default="a_confirmer")
    source = Column(String(200))
    commentaire = Column(Text)
    cree_par = Column(String(20))
    cree_le = Column(DateTime(timezone=True), server_default=func.now())
    confirme_par = Column(String(20))
    confirme_le = Column(DateTime(timezone=True))

    parametre = relationship("Parametre", back_populates="valeurs")


class Referentiel(Base):
    __tablename__ = "referentiels"

    id = Column(Integer, primary_key=True)
    type_ref = Column(String(30), nullable=False)
    code = Column(String(20), nullable=False)
    libelle = Column(String(150), nullable=False)
    extra = Column(JSONB)
    est_actif = Column(Boolean, nullable=False, default=True)
    ordre = Column(Integer, nullable=False, default=0)


class Salarie(Base):
    __tablename__ = "salaries"

    id = Column(Integer, primary_key=True)
    matricule = Column(String(6), unique=True, nullable=False)
    nom = Column(String(100), nullable=False)
    prenoms = Column(String(150))
    sexe = Column(String(1))
    date_naissance = Column(Date)
    lieu_naissance = Column(String(100))
    nationalite = Column(String(60))
    situation_matrimoniale = Column(String(15), nullable=False, default="celibataire")
    nombre_enfants = Column(Integer, nullable=False, default=0)
    nombre_parts = Column(Numeric(3, 1), nullable=False, default=1)
    nombre_personnes_cmu = Column(Integer, nullable=False, default=1)
    telephone = Column(String(30))
    email = Column(String(150))
    adresse = Column(String(200))
    ville = Column(String(80))
    date_embauche = Column(Date)
    date_sortie = Column(Date)
    motif_sortie = Column(String(40))
    type_contrat_id = Column(Integer, ForeignKey("referentiels.id"))
    service_id = Column(Integer, ForeignKey("referentiels.id"))
    section_id = Column(Integer, ForeignKey("referentiels.id"))
    emploi_id = Column(Integer, ForeignKey("referentiels.id"))
    categorie_id = Column(Integer, ForeignKey("referentiels.id"))
    tranche = Column(Integer)
    site_id = Column(Integer, ForeignKey("referentiels.id"))
    type_remuneration = Column(String(10), nullable=False, default="mensuel")
    eligible_heures_sup = Column(Boolean, nullable=False, default=True)
    mode_paiement = Column(String(10), nullable=False, default="virement")
    banque_id = Column(Integer, ForeignKey("referentiels.id"))
    rib_chiffre = Column(Text)
    numero_cnps_chiffre = Column(Text)
    indemnite_transport = Column(Numeric(14, 2))
    solde_conges_initial = Column(Numeric(6, 2), nullable=False, default=0)
    solde_conges_date = Column(Date)
    est_actif = Column(Boolean, nullable=False, default=True)
    cree_le = Column(DateTime(timezone=True), server_default=func.now())
    modifie_le = Column(DateTime(timezone=True), server_default=func.now())

    type_contrat = relationship("Referentiel", foreign_keys=[type_contrat_id], lazy="joined")
    service = relationship("Referentiel", foreign_keys=[service_id], lazy="joined")
    section = relationship("Referentiel", foreign_keys=[section_id], lazy="joined")
    emploi = relationship("Referentiel", foreign_keys=[emploi_id], lazy="joined")
    categorie = relationship("Referentiel", foreign_keys=[categorie_id], lazy="joined")
    site = relationship("Referentiel", foreign_keys=[site_id], lazy="joined")
    banque = relationship("Referentiel", foreign_keys=[banque_id], lazy="joined")
    evolutions = relationship(
        "EvolutionSalaire", cascade="all, delete-orphan", lazy="selectin",
        order_by="EvolutionSalaire.date_effet.desc()", back_populates="salarie",
    )


class EvolutionSalaire(Base):
    __tablename__ = "evolutions_salaire"

    id = Column(Integer, primary_key=True)
    salarie_id = Column(Integer, ForeignKey("salaries.id", ondelete="CASCADE"), nullable=False)
    date_effet = Column(Date, nullable=False)
    montant = Column(Numeric(14, 2), nullable=False)
    sursalaire = Column(Numeric(14, 2), nullable=False, default=0)
    motif = Column(String(200))
    cree_par = Column(String(20))
    cree_le = Column(DateTime(timezone=True), server_default=func.now())
    lot_id = Column(Integer, ForeignKey("augmentations_lots.id", ondelete="SET NULL"))

    salarie = relationship("Salarie", back_populates="evolutions")


class MutationSalarie(Base):
    """Changement d'affectation ou de situation d'un salarié (service, section, emploi, catégorie, site, contrat…)."""
    __tablename__ = "mutations_salaries"

    id = Column(Integer, primary_key=True)
    salarie_id = Column(Integer, ForeignKey("salaries.id", ondelete="CASCADE"), nullable=False)
    date_effet = Column(Date, nullable=False)
    nature = Column(String(20), nullable=False)
    ancienne_valeur = Column(String(150))
    nouvelle_valeur = Column(String(150))
    motif = Column(String(200))
    cree_par = Column(String(20))
    cree_le = Column(DateTime(timezone=True), server_default=func.now())


class EnfantSalarie(Base):
    """Personne à charge déclarée par le salarié (enfant ou conjoint)."""
    __tablename__ = "enfants_salaries"

    id = Column(Integer, primary_key=True)
    salarie_id = Column(Integer, ForeignKey("salaries.id", ondelete="CASCADE"), nullable=False)
    lien = Column(String(10), nullable=False, default="enfant")
    nom = Column(String(100), nullable=False)
    prenoms = Column(String(150))
    sexe = Column(String(1))
    date_naissance = Column(Date)
    a_charge = Column(Boolean, nullable=False, default=True)
    scolarise = Column(Boolean, nullable=False, default=False)
    cree_le = Column(DateTime(timezone=True), server_default=func.now())


class RubriqueFixe(Base):
    """Prime ou retenue récurrente d'un salarié, ajoutée à chaque bulletin mensuel tant qu'elle est en vigueur."""
    __tablename__ = "rubriques_fixes"

    id = Column(Integer, primary_key=True)
    salarie_id = Column(Integer, ForeignKey("salaries.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(6), ForeignKey("rubriques.code"), nullable=False)
    montant = Column(Numeric(14, 2), nullable=False)
    date_debut = Column(Date, nullable=False)
    date_fin = Column(Date)
    commentaire = Column(String(200))
    est_actif = Column(Boolean, nullable=False, default=True)
    cree_par = Column(String(20))
    cree_le = Column(DateTime(timezone=True), server_default=func.now())

    rubrique = relationship("Rubrique", lazy="joined")


class LotAugmentation(Base):
    """Augmentation de salaire appliquée en masse (traçabilité et annulation du lot)."""
    __tablename__ = "augmentations_lots"

    id = Column(Integer, primary_key=True)
    libelle = Column(String(150), nullable=False)
    date_effet = Column(Date, nullable=False)
    mode = Column(String(12), nullable=False)
    valeur = Column(Numeric(14, 2), nullable=False)
    cible = Column(String(12), nullable=False, default="salaire")
    filtres = Column(JSONB)
    nb_salaries = Column(Integer, nullable=False, default=0)
    total_mensuel = Column(Numeric(16, 2), nullable=False, default=0)
    statut = Column(String(10), nullable=False, default="applique")
    cree_par = Column(String(20))
    cree_le = Column(DateTime(timezone=True), server_default=func.now())
    annule_par = Column(String(20))
    annule_le = Column(DateTime(timezone=True))


class JourFerie(Base):
    __tablename__ = "jours_feries"

    jour = Column(Date, primary_key=True)
    libelle = Column(String(100), nullable=False)


class ImportPointages(Base):
    __tablename__ = "imports_pointages"

    id = Column(Integer, primary_key=True)
    nom_fichier = Column(String(200))
    importe_par = Column(String(20))
    importe_le = Column(DateTime(timezone=True), server_default=func.now())
    nb_lignes = Column(Integer, nullable=False, default=0)
    nb_jours = Column(Integer, nullable=False, default=0)
    nb_rejets = Column(Integer, nullable=False, default=0)
    rejets = Column(JSONB)


class Pointage(Base):
    __tablename__ = "pointages"

    id = Column(BigInteger, primary_key=True)
    salarie_id = Column(Integer, ForeignKey("salaries.id"), nullable=False)
    jour = Column(Date, nullable=False)
    heure_entree = Column(Time)
    heure_sortie = Column(Time)
    source = Column(String(10), nullable=False, default="manuel")
    import_id = Column(Integer, ForeignKey("imports_pointages.id", ondelete="SET NULL"))
    commentaire = Column(String(200))
    cree_par = Column(String(20))
    modifie_le = Column(DateTime(timezone=True), server_default=func.now())


class Rubrique(Base):
    __tablename__ = "rubriques"

    code = Column(String(6), primary_key=True)
    libelle = Column(String(100), nullable=False)
    type = Column(String(2), nullable=False)
    montant_defaut = Column(Numeric(14, 2))
    est_actif = Column(Boolean, nullable=False, default=True)


class Campagne(Base):
    __tablename__ = "campagnes"

    id = Column(Integer, primary_key=True)
    libelle = Column(String(100), nullable=False)
    type_campagne = Column(String(15), nullable=False, default="mensuelle")
    nature_bulletin = Column(String(10), nullable=False, default="mensuel")
    annee = Column(Integer, nullable=False)
    mois = Column(Integer, nullable=False)
    numero = Column(Integer, nullable=False, default=1)
    debut = Column(Date, nullable=False)
    fin = Column(Date, nullable=False)
    date_paie = Column(Date)
    statut = Column(String(10), nullable=False, default="ouverte")
    cree_par = Column(String(20))
    cree_le = Column(DateTime(timezone=True), server_default=func.now())
    valide_par = Column(String(20))
    valide_le = Column(DateTime(timezone=True))
    cloture_le = Column(DateTime(timezone=True))


class PresencePeriode(Base):
    __tablename__ = "presences_periode"

    campagne_id = Column(Integer, ForeignKey("campagnes.id", ondelete="CASCADE"), primary_key=True)
    salarie_id = Column(Integer, ForeignKey("salaries.id"), primary_key=True)
    jours_payes = Column(Numeric(5, 1), nullable=False, default=30)
    jours_presence = Column(Numeric(5, 1), nullable=False, default=0)
    heures_travaillees = Column(Numeric(7, 2), nullable=False, default=0)
    hs1 = Column(Numeric(7, 2), nullable=False, default=0)
    hs2 = Column(Numeric(7, 2), nullable=False, default=0)
    hs3 = Column(Numeric(7, 2), nullable=False, default=0)
    hs4 = Column(Numeric(7, 2), nullable=False, default=0)
    heures_absence = Column(Numeric(7, 2), nullable=False, default=0)
    jours_absence_ja = Column(Numeric(5, 1), nullable=False, default=0)
    source = Column(String(10), nullable=False, default="manuel")
    modifie_par = Column(String(20))
    modifie_le = Column(DateTime(timezone=True), server_default=func.now())

    salarie = relationship("Salarie", lazy="joined")


class SaisieRubrique(Base):
    __tablename__ = "saisies_rubriques"

    id = Column(Integer, primary_key=True)
    campagne_id = Column(Integer, ForeignKey("campagnes.id", ondelete="CASCADE"), nullable=False)
    salarie_id = Column(Integer, ForeignKey("salaries.id"), nullable=False)
    code = Column(String(6), ForeignKey("rubriques.code"), nullable=False)
    libelle = Column(String(100), nullable=False)
    type = Column(String(2), nullable=False)
    montant = Column(Numeric(14, 2), nullable=False)
    quantite = Column(Numeric(10, 2))
    commentaire = Column(String(200))
    origine = Column(String(15), nullable=False, default="manuelle")
    reference_id = Column(Integer)
    cree_par = Column(String(20))
    cree_le = Column(DateTime(timezone=True), server_default=func.now())


class Bulletin(Base):
    __tablename__ = "bulletins"

    id = Column(Integer, primary_key=True)
    campagne_id = Column(Integer, ForeignKey("campagnes.id"), nullable=False)
    salarie_id = Column(Integer, ForeignKey("salaries.id"), nullable=False)
    statut = Column(String(10), nullable=False, default="brouillon")
    identite = Column(JSONB, nullable=False)
    entree = Column(JSONB, nullable=False)
    parametres = Column(JSONB, nullable=False)
    lignes = Column(JSONB, nullable=False)
    total_imposable_brut = Column(Numeric(14, 2), nullable=False)
    total_retenues_imposables = Column(Numeric(14, 2), nullable=False)
    total_imposable = Column(Numeric(14, 2), nullable=False)
    cnps = Column(Numeric(14, 2), nullable=False)
    its = Column(Numeric(14, 2), nullable=False)
    total_impots = Column(Numeric(14, 2), nullable=False)
    gains_non_imposables = Column(Numeric(14, 2), nullable=False)
    retenues_non_imposables = Column(Numeric(14, 2), nullable=False)
    net_non_imposable = Column(Numeric(14, 2), nullable=False)
    net_a_payer = Column(Numeric(14, 2), nullable=False)
    charges_patronales = Column(JSONB, nullable=False)
    anomalies = Column(JSONB, nullable=False, default=list)
    calcule_le = Column(DateTime(timezone=True), server_default=func.now())
    valide_par = Column(String(20))
    valide_le = Column(DateTime(timezone=True))
    envoye_le = Column(DateTime(timezone=True))
    lu_le = Column(DateTime(timezone=True))


class Conge(Base):
    __tablename__ = "conges"

    id = Column(Integer, primary_key=True)
    salarie_id = Column(Integer, ForeignKey("salaries.id"), nullable=False)
    type_conge = Column(String(15), nullable=False, default="annuel")
    debut = Column(Date, nullable=False)
    fin = Column(Date, nullable=False)
    jours_ouvrables = Column(Numeric(5, 1), nullable=False)
    statut = Column(String(10), nullable=False, default="demande")
    motif = Column(String(200))
    decide_par = Column(String(20))
    decide_le = Column(DateTime(timezone=True))
    cree_par = Column(String(20))
    cree_le = Column(DateTime(timezone=True), server_default=func.now())

    salarie = relationship("Salarie", lazy="joined")


class Pret(Base):
    __tablename__ = "prets"

    id = Column(Integer, primary_key=True)
    salarie_id = Column(Integer, ForeignKey("salaries.id"), nullable=False)
    type_pret = Column(String(10), nullable=False, default="pret")
    libelle = Column(String(100), nullable=False)
    montant = Column(Numeric(14, 2), nullable=False)
    nombre_echeances = Column(Integer, nullable=False)
    statut = Column(String(10), nullable=False, default="actif")
    cree_par = Column(String(20))
    cree_le = Column(DateTime(timezone=True), server_default=func.now())
    # Clôture anticipée (départ surprise, démission, décès…) : motif, issue (régularisé ou passé en perte) et auteur.
    date_cloture = Column(Date)
    motif_cloture = Column(String(20))
    issue_cloture = Column(String(15))
    commentaire_cloture = Column(String(300))
    cloture_par = Column(String(20))

    salarie = relationship("Salarie", lazy="joined")
    echeances = relationship("EcheancePret", order_by="EcheancePret.annee, EcheancePret.mois", cascade="all, delete-orphan")


class EcheancePret(Base):
    __tablename__ = "echeances_prets"

    id = Column(Integer, primary_key=True)
    pret_id = Column(Integer, ForeignKey("prets.id", ondelete="CASCADE"), nullable=False)
    annee = Column(Integer, nullable=False)
    mois = Column(Integer, nullable=False)
    montant = Column(Numeric(14, 2), nullable=False)
    statut = Column(String(12), nullable=False, default="prevue")
    campagne_id = Column(Integer, ForeignKey("campagnes.id", ondelete="SET NULL"))
    # Règlement hors paie (espèces, chèque, virement…) saisi à la main.
    date_reglement = Column(Date)
    mode_reglement = Column(String(15))
    regle_par = Column(String(20))
    commentaire = Column(String(200))

    pret = relationship("Pret", viewonly=True)


class LotVirement(Base):
    __tablename__ = "lots_virement"

    id = Column(Integer, primary_key=True)
    campagne_id = Column(Integer, ForeignKey("campagnes.id"), nullable=False)
    libelle = Column(String(120), nullable=False)
    date_valeur = Column(Date)
    statut = Column(String(10), nullable=False, default="prepare")
    nombre_ordres = Column(Integer, nullable=False, default=0)
    total = Column(Numeric(16, 2), nullable=False, default=0)
    exclus = Column(JSONB, nullable=False, default=list)
    cree_par = Column(String(20))
    cree_le = Column(DateTime(timezone=True), server_default=func.now())
    lance_par = Column(String(20))
    lance_le = Column(DateTime(timezone=True))

    ordres = relationship("OrdreVirement", cascade="all, delete-orphan", order_by="OrdreVirement.id")


class OrdreVirement(Base):
    __tablename__ = "ordres_virement"

    id = Column(Integer, primary_key=True)
    lot_id = Column(Integer, ForeignKey("lots_virement.id", ondelete="CASCADE"), nullable=False)
    salarie_id = Column(Integer, ForeignKey("salaries.id"), nullable=False)
    bulletin_id = Column(Integer, ForeignKey("bulletins.id"))
    montant = Column(Numeric(14, 2), nullable=False)
    banque = Column(String(100))
    rib_chiffre = Column(Text, nullable=False)

    salarie = relationship("Salarie", lazy="joined")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    type_notif = Column(String(20), nullable=False)
    destinataire = Column(String(200))
    objet = Column(String(200), nullable=False)
    statut = Column(String(12), nullable=False, default="en_attente")
    erreur = Column(String(300))
    tentatives = Column(Integer, nullable=False, default=0)
    campagne_id = Column(Integer, ForeignKey("campagnes.id", ondelete="SET NULL"))
    bulletin_id = Column(Integer, ForeignKey("bulletins.id", ondelete="SET NULL"))
    cree_par = Column(String(20))
    cree_le = Column(DateTime(timezone=True), server_default=func.now())
    envoye_le = Column(DateTime(timezone=True))


class MesureDisciplinaire(Base):
    __tablename__ = "mesures_disciplinaires"

    id = Column(Integer, primary_key=True)
    reference = Column(String(20))
    salarie_id = Column(Integer, ForeignKey("salaries.id"), nullable=False)
    type_mesure = Column(String(15), nullable=False)
    date_faits = Column(Date)
    date_decision = Column(Date, nullable=False)
    motif = Column(Text, nullable=False)
    debut_mise_a_pied = Column(Date)
    fin_mise_a_pied = Column(Date)
    statut = Column(String(10), nullable=False, default="active")
    cree_par = Column(String(20))
    cree_le = Column(DateTime(timezone=True), server_default=func.now())
    annule_par = Column(String(20))
    annule_le = Column(DateTime(timezone=True))
    motif_annulation = Column(String(200))

    salarie = relationship("Salarie", lazy="joined")


class NoteService(Base):
    __tablename__ = "notes_service"

    id = Column(Integer, primary_key=True)
    reference = Column(String(20))
    objet = Column(String(150), nullable=False)
    contenu = Column(Text, nullable=False)
    date_effet = Column(Date, nullable=False)
    service_id = Column(Integer, ForeignKey("referentiels.id"))
    statut = Column(String(10), nullable=False, default="active")
    cree_par = Column(String(20))
    cree_le = Column(DateTime(timezone=True), server_default=func.now())

    service = relationship("Referentiel", lazy="joined")


class Exercice(Base):
    """Année de paie clôturée : verrouille les écritures datées de l'année et fige les cumuls par salarié."""
    __tablename__ = "exercices"

    annee = Column(Integer, primary_key=True)
    statut = Column(String(10), nullable=False, default="cloture")
    cloture_le = Column(DateTime(timezone=True))
    cloture_par = Column(String(20))
    instantane = Column(JSONB)
    rouvert_le = Column(DateTime(timezone=True))
    rouvert_par = Column(String(20))
    motif_reouverture = Column(String(300))


class GrilleTranche(Base):
    __tablename__ = "grille_tranches"

    numero = Column(Integer, primary_key=True)
    libelle = Column(String(60), nullable=False)
    heures = Column(Numeric(10, 4), nullable=False)
    coefficient = Column(Numeric(8, 4), nullable=False, default=1)
    modifie_par = Column(String(20))
    modifie_le = Column(DateTime(timezone=True))


class GrilleCategorie(Base):
    __tablename__ = "grille_categories"

    id = Column(Integer, primary_key=True)
    categorie_id = Column(Integer, ForeignKey("referentiels.id"), nullable=False)
    date_effet = Column(Date, nullable=False)
    base_horaire = Column(Numeric(12, 4), nullable=False)
    cree_par = Column(String(20))
    cree_le = Column(DateTime(timezone=True), server_default=func.now())
