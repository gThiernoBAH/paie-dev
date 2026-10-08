from datetime import datetime
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
