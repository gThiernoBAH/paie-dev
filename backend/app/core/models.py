from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
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
    site_id = Column(Integer, ForeignKey("referentiels.id"))
    type_remuneration = Column(String(10), nullable=False, default="mensuel")
    eligible_heures_sup = Column(Boolean, nullable=False, default=True)
    mode_paiement = Column(String(10), nullable=False, default="virement")
    banque_id = Column(Integer, ForeignKey("referentiels.id"))
    rib_chiffre = Column(Text)
    numero_cnps_chiffre = Column(Text)
    indemnite_transport = Column(Numeric(14, 2))
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

    salarie = relationship("Salarie", back_populates="evolutions")
