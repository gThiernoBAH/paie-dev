from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core import models, schemas
from ..core.database import get_db
from ..services import audit
from .auth_routes import require_permission

router = APIRouter(prefix="/referentiels", tags=["Référentiels"])


@router.get("", response_model=list[schemas.ReferentielOut])
def lister(
    type_ref: Optional[str] = Query(default=None, max_length=30),
    inclure_inactifs: bool = False,
    db: Session = Depends(get_db),
    _: models.Utilisateur = Depends(require_permission("voir_salaries")),
):
    requete = db.query(models.Referentiel)
    if type_ref:
        requete = requete.filter(models.Referentiel.type_ref == type_ref)
    if not inclure_inactifs:
        requete = requete.filter(models.Referentiel.est_actif.is_(True))
    return requete.order_by(models.Referentiel.type_ref, models.Referentiel.ordre, models.Referentiel.libelle).all()


@router.post("", response_model=schemas.ReferentielOut, status_code=201)
def creer(
    corps: schemas.ReferentielIn, request: Request, db: Session = Depends(get_db),
    acteur: models.Utilisateur = Depends(require_permission("modifier_salaries")),
):
    if corps.type_ref not in schemas.TYPES_REFERENTIEL:
        raise HTTPException(status_code=422, detail="Type de liste inconnu.")
    ligne = models.Referentiel(
        type_ref=corps.type_ref, code=corps.code.upper(), libelle=corps.libelle.strip(),
        extra=corps.extra, ordre=corps.ordre, est_actif=True,
    )
    db.add(ligne)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ce code existe déjà dans cette liste.")
    audit.enregistrer(db, "referentiel_cree", acteur=acteur, cible_type="referentiel", cible_id=ligne.id,
                      detail={"type": ligne.type_ref, "code": ligne.code}, request=request)
    db.commit()
    db.refresh(ligne)
    return ligne


@router.patch("/{ref_id}", response_model=schemas.ReferentielOut)
def modifier(
    ref_id: int, corps: schemas.ReferentielModifIn, request: Request, db: Session = Depends(get_db),
    acteur: models.Utilisateur = Depends(require_permission("modifier_salaries")),
):
    ligne = db.get(models.Referentiel, ref_id)
    if ligne is None:
        raise HTTPException(status_code=404, detail="Élément introuvable.")
    changements = corps.model_dump(exclude_unset=True)
    for champ, valeur in changements.items():
        setattr(ligne, champ, valeur.strip() if isinstance(valeur, str) else valeur)
    audit.enregistrer(db, "referentiel_modifie", acteur=acteur, cible_type="referentiel", cible_id=ligne.id,
                      detail={"type": ligne.type_ref, "code": ligne.code, "champs": sorted(changements)}, request=request)
    db.commit()
    db.refresh(ligne)
    return ligne
