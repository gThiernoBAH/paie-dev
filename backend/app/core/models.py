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
