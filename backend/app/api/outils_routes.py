"""Outils de gestion : augmentations de salaire en masse et simulation de bulletin."""
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core import models
from ..core.database import get_db
from ..services import audit
from ..services import augmentations as svc_aug
from ..services import simulation as svc_sim
from ..services.bulletins import ErreurPaie
from .auth_routes import a_la_permission, require_permission

router = APIRouter(tags=["Outils"])
SENSIBLE = require_permission("voir_donnees_sensibles")


def _exiger_modification(acteur: models.Utilisateur) -> None:
    if not a_la_permission(acteur, "modifier_salaries"):
        raise HTTPException(status_code=403, detail="Permission manquante : modifier_salaries")


# ----------------------------------------------------------------- augmentations en masse
class FiltresIn(BaseModel):
    service_id: Optional[int] = None
    section_id: Optional[int] = None
    emploi_id: Optional[int] = None
    categorie_id: Optional[int] = None
    type_contrat_id: Optional[int] = None
    site_id: Optional[int] = None
    type_remuneration: Optional[str] = Field(default=None, pattern="^(mensuel|journalier)$")
    salarie_ids: Optional[list[int]] = None


class AugmentationIn(BaseModel):
    libelle: str = Field(min_length=3, max_length=150)
    filtres: FiltresIn = FiltresIn()
    mode: str = Field(pattern="^(pourcentage|montant)$")
    valeur: Decimal = Field(gt=0, le=Decimal("100000000"))
    cible: str = Field(default="salaire", pattern="^(salaire|sursalaire|les_deux)$")
    date_effet: date
    arrondi: int = Field(default=1)


def _lot_sortie(l: models.LotAugmentation) -> dict:
    return {"id": l.id, "libelle": l.libelle, "date_effet": l.date_effet, "mode": l.mode, "valeur": l.valeur, "cible": l.cible,
            "filtres": l.filtres, "nb_salaries": l.nb_salaries, "total_mensuel": l.total_mensuel, "statut": l.statut,
            "cree_par": l.cree_par, "cree_le": l.cree_le, "annule_par": l.annule_par}


@router.post("/augmentations/apercu")
def apercu_augmentation(corps: AugmentationIn, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(SENSIBLE)):
    _exiger_modification(acteur)
    try:
        return svc_aug.apercu(db, corps.filtres.model_dump(exclude_none=True), corps.mode, corps.valeur, corps.cible, corps.date_effet, corps.arrondi)
    except svc_aug.ErreurAugmentation as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/augmentations", status_code=201)
def appliquer_augmentation(corps: AugmentationIn, request: Request, db: Session = Depends(get_db),
                           acteur: models.Utilisateur = Depends(SENSIBLE)):
    _exiger_modification(acteur)
    try:
        lot = svc_aug.appliquer(db, corps.libelle.strip(), corps.filtres.model_dump(exclude_none=True), corps.mode, corps.valeur,
                                corps.cible, corps.date_effet, corps.arrondi, acteur)
    except svc_aug.ErreurAugmentation as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    audit.enregistrer(db, "augmentation_appliquee", acteur=acteur, cible_type="augmentation", cible_id=lot.id,
                      detail={"libelle": lot.libelle, "mode": lot.mode, "valeur": str(lot.valeur), "salaries": lot.nb_salaries,
                              "date_effet": lot.date_effet.isoformat()}, request=request)
    db.commit()
    db.refresh(lot)
    return _lot_sortie(lot)


@router.get("/augmentations")
def lister_augmentations(db: Session = Depends(get_db), _=Depends(SENSIBLE)):
    return [_lot_sortie(l) for l in db.query(models.LotAugmentation).order_by(models.LotAugmentation.id.desc()).limit(100).all()]


@router.post("/augmentations/{lot_id}/annuler")
def annuler_augmentation(lot_id: int, request: Request, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(SENSIBLE)):
    _exiger_modification(acteur)
    lot = db.get(models.LotAugmentation, lot_id)
    if lot is None:
        raise HTTPException(status_code=404, detail="Lot introuvable.")
    try:
        n = svc_aug.annuler(db, lot, acteur)
    except svc_aug.ErreurAugmentation as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    audit.enregistrer(db, "augmentation_annulee", acteur=acteur, cible_type="augmentation", cible_id=lot.id,
                      detail={"libelle": lot.libelle, "evolutions_supprimees": n}, request=request)
    db.commit()
    return _lot_sortie(lot)


# ----------------------------------------------------------------- simulation de bulletin
class RubriqueSimIn(BaseModel):
    code: str = Field(min_length=1, max_length=6)
    libelle: Optional[str] = Field(default=None, max_length=100)
    type: str = Field(pattern="^(GI|GN|RI|RN)$")
    montant: Decimal = Field(ge=0, le=Decimal("1000000000"))


class SimulationIn(BaseModel):
    annee: int = Field(ge=2000, le=2100)
    mois: int = Field(ge=1, le=12)
    salarie_id: Optional[int] = None
    nature: Optional[str] = Field(default=None, pattern="^(mensuel|journalier)$")
    salaire_categoriel: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("1000000000"))
    sursalaire: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("1000000000"))
    parts: Optional[Decimal] = Field(default=None, ge=1, le=5)
    personnes_cmu: Optional[int] = Field(default=None, ge=0, le=30)
    date_entree: Optional[date] = None
    jours_payes: Decimal = Field(default=Decimal(30), ge=0, le=31)
    jours_absence: Decimal = Field(default=Decimal(0), ge=0, le=31)
    heures_absence: Decimal = Field(default=Decimal(0), ge=0, le=500)
    heures_travaillees: Decimal = Field(default=Decimal(0), ge=0, le=500)
    jours_presence: Decimal = Field(default=Decimal(0), ge=0, le=31)
    hs1: Decimal = Field(default=Decimal(0), ge=0, le=300)
    hs2: Decimal = Field(default=Decimal(0), ge=0, le=300)
    hs3: Decimal = Field(default=Decimal(0), ge=0, le=300)
    hs4: Decimal = Field(default=Decimal(0), ge=0, le=300)
    inclure_rubriques_fixes: bool = True
    rubriques: list[RubriqueSimIn] = Field(default_factory=list, max_length=30)


@router.post("/simulation/bulletin")
def simuler_bulletin(corps: SimulationIn, request: Request, db: Session = Depends(get_db),
                     acteur: models.Utilisateur = Depends(require_permission("lancer_paie"))):
    """Calcule un bulletin hypothétique ; rien n'est enregistré (seul l'usage est tracé)."""
    if not a_la_permission(acteur, "voir_donnees_sensibles"):
        raise HTTPException(status_code=403, detail="Permission manquante : voir_donnees_sensibles")
    salarie = None
    if corps.salarie_id:
        salarie = db.get(models.Salarie, corps.salarie_id)
        if salarie is None:
            raise HTTPException(status_code=404, detail="Salarié introuvable.")
    h = corps.model_dump(exclude={"annee", "mois", "salarie_id"})
    h["rubriques"] = [r.model_dump() for r in corps.rubriques]
    try:
        r = svc_sim.simuler(db, corps.annee, corps.mois, salarie, h)
    except ErreurPaie as e:
        raise HTTPException(status_code=e.statut, detail=str(e))
    audit.enregistrer(db, "simulation_bulletin", acteur=acteur, cible_type="salarie", cible_id=salarie.id if salarie else None,
                      detail={"periode": f"{corps.mois:02d}/{corps.annee}", "matricule": salarie.matricule if salarie else None}, request=request)
    db.commit()
    return r
