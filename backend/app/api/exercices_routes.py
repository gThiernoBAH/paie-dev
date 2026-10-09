"""Clôture annuelle."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core import models
from ..core.database import get_db
from ..services import audit
from ..services import exercices as svc
from .auth_routes import require_permission

router = APIRouter(prefix="/exercices", tags=["Clôture annuelle"])
VOIR = require_permission("valider_bulletins")


class ReouvertureIn(BaseModel):
    motif: str = Field(min_length=5, max_length=300)


@router.get("")
def lister(db: Session = Depends(get_db), _=Depends(VOIR)):
    return svc.liste(db)


@router.get("/{annee}")
def detail(annee: int, db: Session = Depends(get_db), _=Depends(VOIR)):
    e = db.get(models.Exercice, annee)
    return {"annee": annee, "statut": e.statut if e else "ouvert", "raisons": [] if (e and e.statut == "cloture") else svc.prerequis(db, annee),
            "cloture_le": e.cloture_le if e else None, "cloture_par": e.cloture_par if e else None,
            "instantane": e.instantane if (e and e.statut == "cloture") else None}


@router.post("/{annee}/cloturer")
def cloturer(annee: int, request: Request, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(VOIR)):
    try:
        e = svc.cloturer(db, annee, acteur)
    except svc.ErreurExercice as x:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(x))
    audit.enregistrer(db, "exercice_cloture", acteur=acteur, cible_type="exercice", cible_id=annee,
                      detail={"salaries": len(e.instantane["lignes"])}, request=request)
    db.commit()
    return {"annee": annee, "statut": e.statut, "salaries": len(e.instantane["lignes"])}


@router.post("/{annee}/rouvrir")
def rouvrir(annee: int, corps: ReouvertureIn, request: Request, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(VOIR)):
    if acteur.role != "admin":
        raise HTTPException(status_code=403, detail="Seul un administrateur peut rouvrir un exercice clôturé.")
    try:
        e = svc.rouvrir(db, annee, acteur, corps.motif.strip())
    except svc.ErreurExercice as x:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(x))
    audit.enregistrer(db, "exercice_rouvert", acteur=acteur, cible_type="exercice", cible_id=annee, detail={"motif": corps.motif.strip()}, request=request)
    db.commit()
    return {"annee": annee, "statut": e.statut}
