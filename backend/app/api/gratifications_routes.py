"""Gratifications : saisie groupée d'une rubrique (GRT par défaut) pour les salariés d'une campagne."""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core import models
from ..core.database import get_db
from ..services import audit
from ..services import salaries as svc_salaries
from .auth_routes import require_permission

router = APIRouter(tags=["Gratifications"])
GERER = require_permission("lancer_paie")
ORIGINE = "gratification"
CODE_DEFAUT = "GRT"


def _campagne_modifiable(db: Session, cid: int) -> models.Campagne:
    c = db.get(models.Campagne, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="Campagne introuvable.")
    if c.statut in ("validee", "cloturee"):
        raise HTTPException(status_code=409, detail="Campagne validée : modification impossible.")
    return c


def _rubrique(db: Session, code: str) -> models.Rubrique:
    r = db.get(models.Rubrique, code.upper())
    if r is None or not r.est_actif or r.type not in ("GI", "GN"):
        raise HTTPException(status_code=422, detail="Rubrique inconnue, inactive ou qui n'est pas un gain.")
    return r


@router.get("/campagnes/{cid}/gratifications")
def lister(cid: int, code: str = CODE_DEFAUT, db: Session = Depends(get_db), _=Depends(GERER)):
    c = db.get(models.Campagne, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="Campagne introuvable.")
    existantes = {s.salarie_id: s for s in db.query(models.SaisieRubrique).filter_by(campagne_id=cid, origine=ORIGINE, code=code.upper()).all()}
    lignes = []
    for p in db.query(models.PresencePeriode).filter_by(campagne_id=cid).all():
        s = p.salarie
        e = existantes.get(s.id)
        lignes.append({"salarie_id": s.id, "matricule": s.matricule, "nom": f"{s.nom} {s.prenoms or ''}".strip(),
                       "service": s.service.libelle if s.service else None, "service_id": s.service_id,
                       "montant": e.montant if e else None, "commentaire": e.commentaire if e else None})
    lignes.sort(key=lambda x: x["matricule"])
    return {"campagne": {"id": c.id, "libelle": c.libelle, "statut": c.statut}, "code": code.upper(), "salaries": lignes}


class ProposerIn(BaseModel):
    mode: str = Field(pattern="^(fixe|pourcentage_salaire)$")
    valeur: Decimal = Field(gt=0, le=100_000_000)
    service_id: Optional[int] = None


@router.post("/campagnes/{cid}/gratifications/proposer")
def proposer(cid: int, corps: ProposerIn, db: Session = Depends(get_db), _=Depends(GERER)):
    """Montants proposés (rien n'est enregistré). % : du salaire catégoriel + sursalaire en vigueur en fin de période."""
    c = db.get(models.Campagne, cid)
    if c is None:
        raise HTTPException(status_code=404, detail="Campagne introuvable.")
    if corps.mode == "pourcentage_salaire" and corps.valeur > 1000:
        raise HTTPException(status_code=422, detail="Pourcentage invraisemblable.")
    montants, sans_salaire = {}, []
    for p in db.query(models.PresencePeriode).filter_by(campagne_id=cid).all():
        s = p.salarie
        if corps.service_id and s.service_id != corps.service_id:
            continue
        if corps.mode == "fixe":
            montants[s.id] = corps.valeur
        else:
            e = svc_salaries.salaire_en_vigueur(s, c.fin)
            if e is None:
                sans_salaire.append(s.matricule)
                continue
            montants[s.id] = ((e.montant + (e.sursalaire or 0)) * corps.valeur / 100).quantize(Decimal("0.01"))
    return {"montants": montants, "sans_salaire": sans_salaire}


class LigneIn(BaseModel):
    salarie_id: int
    montant: Optional[Decimal] = Field(default=None, ge=0, le=100_000_000_000)
    commentaire: Optional[str] = Field(default=None, max_length=200)


class EnregistrerIn(BaseModel):
    code: str = CODE_DEFAUT
    lignes: list[LigneIn] = Field(max_length=20000)


@router.put("/campagnes/{cid}/gratifications")
def enregistrer(cid: int, corps: EnregistrerIn, request: Request, db: Session = Depends(get_db),
                acteur: models.Utilisateur = Depends(GERER)):
    """Remplace les gratifications saisies ici pour les salariés listés (montant vide ou 0 = suppression)."""
    c = _campagne_modifiable(db, cid)
    r = _rubrique(db, corps.code)
    presents = {p.salarie_id for p in db.query(models.PresencePeriode).filter_by(campagne_id=cid).all()}
    inconnus = [l.salarie_id for l in corps.lignes if l.salarie_id not in presents]
    if inconnus:
        raise HTTPException(status_code=422, detail="Certains salariés ne sont pas dans cette campagne.")
    ids = {l.salarie_id for l in corps.lignes}
    db.query(models.SaisieRubrique).filter(models.SaisieRubrique.campagne_id == cid, models.SaisieRubrique.origine == ORIGINE,
                                           models.SaisieRubrique.code == r.code, models.SaisieRubrique.salarie_id.in_(ids or {0})
                                           ).delete(synchronize_session=False)
    n, total = 0, Decimal(0)
    for l in corps.lignes:
        if l.montant and l.montant > 0:
            db.add(models.SaisieRubrique(campagne_id=cid, salarie_id=l.salarie_id, code=r.code, libelle=r.libelle, type=r.type,
                                         montant=l.montant, commentaire=l.commentaire, origine=ORIGINE, cree_par=acteur.identifiant))
            n += 1
            total += l.montant
    audit.enregistrer(db, "gratifications_enregistrees", acteur=acteur, cible_type="campagne", cible_id=c.id,
                      detail={"code": r.code, "salaries": n, "total": str(total)}, request=request)
    db.commit()
    return {"enregistrees": n, "total": total}
