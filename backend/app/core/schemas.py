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


# --- Référentiels et salariés (lot 2) ---
TYPES_REFERENTIEL = ("service", "section", "emploi", "categorie", "site", "banque", "type_contrat")


class ReferentielOut(BaseModel):
    id: int
    type_ref: str
    code: str
    libelle: str
    extra: Optional[dict] = None
    est_actif: bool
    ordre: int
    model_config = ConfigDict(from_attributes=True)


class ReferentielIn(BaseModel):
    type_ref: str
    code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_.\-]+$")
    libelle: str = Field(min_length=1, max_length=150)
    extra: Optional[dict] = None
    ordre: int = Field(default=0, ge=0, le=100000)


class ReferentielModifIn(BaseModel):
    libelle: Optional[str] = Field(default=None, min_length=1, max_length=150)
    extra: Optional[dict] = None
    est_actif: Optional[bool] = None
    ordre: Optional[int] = Field(default=None, ge=0, le=100000)


class RefCourtOut(BaseModel):
    id: int
    code: str
    libelle: str
    model_config = ConfigDict(from_attributes=True)


class SalarieChampsIn(BaseModel):
    """Champs modifiables d'une fiche (tous facultatifs en modification)."""
    nom: Optional[str] = Field(default=None, min_length=1, max_length=100)
    prenoms: Optional[str] = Field(default=None, max_length=150)
    sexe: Optional[str] = Field(default=None, pattern=r"^[MF]$")
    date_naissance: Optional[date] = None
    lieu_naissance: Optional[str] = Field(default=None, max_length=100)
    nationalite: Optional[str] = Field(default=None, max_length=60)
    situation_matrimoniale: Optional[str] = Field(default=None, pattern=r"^(celibataire|marie|divorce|veuf)$")
    nombre_enfants: Optional[int] = Field(default=None, ge=0, le=30)
    nombre_parts: Optional[float] = Field(default=None, ge=1, le=5)
    nombre_personnes_cmu: Optional[int] = Field(default=None, ge=0, le=30)
    indemnite_transport: Optional[float] = Field(default=None, ge=0, le=10_000_000)
    telephone: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=150)
    adresse: Optional[str] = Field(default=None, max_length=200)
    ville: Optional[str] = Field(default=None, max_length=80)
    date_embauche: Optional[date] = None
    type_contrat_id: Optional[int] = None
    service_id: Optional[int] = None
    section_id: Optional[int] = None
    emploi_id: Optional[int] = None
    categorie_id: Optional[int] = None
    site_id: Optional[int] = None
    type_remuneration: Optional[str] = Field(default=None, pattern=r"^(mensuel|journalier)$")
    eligible_heures_sup: Optional[bool] = None
    mode_paiement: Optional[str] = Field(default=None, pattern=r"^(virement|especes|cheque)$")
    banque_id: Optional[int] = None
    # Données sensibles : exigent le droit « voir_donnees_sensibles ».
    rib: Optional[str] = Field(default=None, max_length=40)
    numero_cnps: Optional[str] = Field(default=None, max_length=30)


class SalarieCreationIn(SalarieChampsIn):
    matricule: Optional[str] = Field(default=None, max_length=6)  # vide = prochain matricule libre
    nom: str = Field(min_length=1, max_length=100)
    salaire_base: Optional[float] = Field(default=None, ge=0)     # exige « voir_donnees_sensibles »
    sursalaire: Optional[float] = Field(default=None, ge=0)


class SalarieListeOut(BaseModel):
    id: int
    matricule: str
    nom: str
    prenoms: Optional[str] = None
    service: Optional[RefCourtOut] = None
    emploi: Optional[RefCourtOut] = None
    type_remuneration: str
    date_embauche: Optional[date] = None
    date_sortie: Optional[date] = None
    est_actif: bool
    model_config = ConfigDict(from_attributes=True)


class SalariePageOut(BaseModel):
    total: int
    page: int
    taille: int
    elements: list[SalarieListeOut]


class EvolutionSalaireOut(BaseModel):
    id: int
    date_effet: date
    montant: float
    sursalaire: float = 0
    motif: Optional[str] = None
    cree_par: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class EvolutionSalaireIn(BaseModel):
    date_effet: date
    montant: float = Field(ge=0, le=1_000_000_000)
    sursalaire: float = Field(default=0, ge=0, le=1_000_000_000)
    motif: Optional[str] = Field(default=None, max_length=200)


class SortieIn(BaseModel):
    date_sortie: date
    motif_sortie: str = Field(min_length=2, max_length=40)


# --- Pointages, rubriques, jours fériés (lot 4) ---
class PointageOut(BaseModel):
    id: int
    salarie_id: int
    matricule: str
    nom: str
    jour: date
    heure_entree: Optional[str] = None
    heure_sortie: Optional[str] = None
    source: str
    commentaire: Optional[str] = None


class PointageIn(BaseModel):
    salarie_id: int
    jour: date
    heure_entree: Optional[str] = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    heure_sortie: Optional[str] = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    commentaire: Optional[str] = Field(default=None, max_length=200)


class ImportPointagesIn(BaseModel):
    nom_fichier: str = Field(default="import.csv", max_length=200)
    contenu: str = Field(min_length=1, max_length=5_000_000)


class JourFerieIn(BaseModel):
    jour: date
    libelle: str = Field(min_length=1, max_length=100)


class RubriqueIn(BaseModel):
    code: str = Field(min_length=1, max_length=6, pattern=r"^[A-Za-z0-9]+$")
    libelle: str = Field(min_length=1, max_length=100)
    type: str = Field(pattern=r"^(GI|GN|RI|RN)$")
    montant_defaut: Optional[float] = Field(default=None, ge=0)


class RubriqueModifIn(BaseModel):
    libelle: Optional[str] = Field(default=None, min_length=1, max_length=100)
    montant_defaut: Optional[float] = Field(default=None, ge=0)
    est_actif: Optional[bool] = None
