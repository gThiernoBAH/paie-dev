"""Grille salariale : tranches horaires, base horaire par catégorie, import, position d'un salarié."""
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core import models
from ..core.database import get_db
from ..services import audit
from ..services import grille as svc
from .auth_routes import a_la_permission, require_permission

router = APIRouter(tags=["Grille salariale"])
SENSIBLE = require_permission("voir_donnees_sensibles")


def _ecriture(acteur: models.Utilisateur) -> None:
    if not a_la_permission(acteur, "gerer_parametres"):
        raise HTTPException(status_code=403, detail="Permission manquante : gerer_parametres")


class TrancheIn(BaseModel):
    numero: int = Field(ge=1, le=5)
    libelle: str = Field(min_length=1, max_length=60)
    heures: Decimal = Field(ge=0, le=Decimal("744"))
    coefficient: Decimal = Field(gt=0, le=Decimal("10"))


class BaseIn(BaseModel):
    date_effet: date
    base_horaire: Decimal = Field(gt=0, le=Decimal("1000000"))


class ImportIn(BaseModel):
    contenu: str = Field(min_length=3, max_length=500_000)
    date_effet: date
    appliquer: bool = False


@router.get("/grille/tranches")
def lire_tranches(db: Session = Depends(get_db), _=Depends(SENSIBLE)):
    return svc.tranches(db)


@router.put("/grille/tranches")
def ecrire_tranches(corps: list[TrancheIn], request: Request, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(SENSIBLE)):
    _ecriture(acteur)
    try:
        svc.modifier_tranches(db, [c.model_dump() for c in corps], acteur)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    audit.enregistrer(db, "grille_tranches_modifiees", acteur=acteur, cible_type="grille", cible_id="tranches", request=request)
    db.commit()
    return svc.tranches(db)


@router.get("/grille/categories")
def lire_categories(date_effet: Optional[date] = None, db: Session = Depends(get_db), _=Depends(SENSIBLE)):
    return svc.vue_categories(db, date_effet)


@router.put("/grille/categories/{categorie_id}")
def ecrire_base(categorie_id: int, corps: BaseIn, request: Request, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(SENSIBLE)):
    _ecriture(acteur)
    try:
        g = svc.enregistrer_base(db, categorie_id, corps.date_effet, corps.base_horaire, acteur)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    audit.enregistrer(db, "grille_base_modifiee", acteur=acteur, cible_type="categorie", cible_id=categorie_id,
                      detail={"date_effet": corps.date_effet.isoformat(), "base_horaire": str(corps.base_horaire)}, request=request)
    db.commit()
    return {"categorie_id": g.categorie_id, "date_effet": g.date_effet, "base_horaire": g.base_horaire}


@router.get("/grille/categories/{categorie_id}/historique")
def historique_base(categorie_id: int, db: Session = Depends(get_db), _=Depends(SENSIBLE)):
    lignes = db.query(models.GrilleCategorie).filter_by(categorie_id=categorie_id).order_by(models.GrilleCategorie.date_effet.desc()).all()
    return [{"date_effet": g.date_effet, "base_horaire": g.base_horaire, "cree_par": g.cree_par} for g in lignes]


@router.post("/grille/import")
def importer(corps: ImportIn, request: Request, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(SENSIBLE)):
    """Aperçu (appliquer = false) puis application d'un tableau CATEGORIE / BASE HEURE copié depuis le legacy ou Excel."""
    _ecriture(acteur)
    try:
        r = svc.importer(db, corps.contenu, corps.date_effet, corps.appliquer, acteur)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    if corps.appliquer:
        audit.enregistrer(db, "grille_importee", acteur=acteur, cible_type="grille", cible_id="categories",
                          detail={"date_effet": corps.date_effet.isoformat(), "lignes": r["appliquees"]}, request=request)
    db.commit()
    return r


@router.get("/salaries/{salarie_id}/grille")
def position(salarie_id: int, db: Session = Depends(get_db), _=Depends(SENSIBLE)):
    s = db.get(models.Salarie, salarie_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Salarié introuvable.")
    return svc.situation(db, s)
