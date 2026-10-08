from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .permissions import ROLES


class ConnexionIn(BaseModel):
    identifiant: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=1, max_length=200)


class UtilisateurOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    identifiant: str
    nom: str
    prenom: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    role: str
    est_actif: bool
    doit_changer_mot_de_passe: bool
    derniere_connexion: Optional[datetime] = None
    permissions: list[str] = []


class SessionOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: int
    user: UtilisateurOut


class ChangerMotDePasseIn(BaseModel):
    ancien_mot_de_passe: str = Field(min_length=1, max_length=200)
    nouveau_mot_de_passe: str = Field(min_length=1, max_length=200)


class UtilisateurCreationIn(BaseModel):
    identifiant: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_.-]+$")
    nom: str = Field(min_length=1, max_length=100)
    prenom: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None, max_length=150)
    telephone: Optional[str] = Field(default=None, max_length=30)
    role: str = "salarie"


class UtilisateurModificationIn(BaseModel):
    nom: Optional[str] = Field(default=None, min_length=1, max_length=100)
    prenom: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None, max_length=150)
    telephone: Optional[str] = Field(default=None, max_length=30)
    role: Optional[str] = None
    est_actif: Optional[bool] = None


class PermissionsIn(BaseModel):
    permissions: list[str]


class MotDePasseTemporaireOut(BaseModel):
    utilisateur: UtilisateurOut
    mot_de_passe_temporaire: str


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    horodatage: datetime
    acteur_identifiant: Optional[str] = None
    action: str
    cible_type: Optional[str] = None
    cible_id: Optional[str] = None
    detail: Optional[Any] = None
    adresse_ip: Optional[str] = None


class AuditPageOut(BaseModel):
    total: int
    page: int
    taille: int
    elements: list[AuditOut]


def role_valide(role: str) -> bool:
    return role in ROLES


# --- Paramétrage (lot 1) ---
class ValeurParametreOut(BaseModel):
    id: int
    valeur: str
    date_effet: date
    statut: str
    source: Optional[str] = None
    commentaire: Optional[str] = None
    cree_par: Optional[str] = None
    cree_le: Optional[datetime] = None
    confirme_par: Optional[str] = None
    confirme_le: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class ParametreOut(BaseModel):
    cle: str
    categorie: str
    libelle: str
    description: Optional[str] = None
    type_valeur: str
    unite: Optional[str] = None
    valeur_min: Optional[float] = None
    valeur_max: Optional[float] = None
    choix: Optional[list[str]] = None
    critique: bool
    valeur_courante: Optional[ValeurParametreOut] = None
    nb_valeurs: int


class ParametreDetailOut(ParametreOut):
    historique: list[ValeurParametreOut]


class ValeurParametreIn(BaseModel):
    valeur: str = Field(min_length=1, max_length=5000)
    date_effet: date
    statut: str = Field(default="confirme", pattern=r"^(confirme|a_confirmer)$")
    source: Optional[str] = Field(default=None, max_length=200)
    commentaire: Optional[str] = Field(default=None, max_length=1000)


class EtatParametresOut(BaseModel):
    total: int
    a_confirmer: int
    critiques_a_confirmer: int
    cles_critiques: list[str]


class ConfirmationIn(BaseModel):
    source: str = Field(min_length=3, max_length=200)
