"""Virements de paie."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core import models
from ..core.database import get_db
from ..services import audit, fichiers, messagerie
from ..services import virements as svc
from ..services.bulletins import ErreurPaie
from .auth_routes import require_permission

router = APIRouter(tags=["Virements"])
GERER = require_permission("gerer_virements")


class LotIn(BaseModel):
    date_valeur: Optional[date] = None


def _lot(db: Session, lot_id: int) -> models.LotVirement:
    lot = db.get(models.LotVirement, lot_id)
    if lot is None:
        raise HTTPException(status_code=404, detail="Lot de virement introuvable.")
    return lot


def _sortie(lot: models.LotVirement, detail: bool = False) -> dict:
    d = {"id": lot.id, "campagne_id": lot.campagne_id, "libelle": lot.libelle, "date_valeur": lot.date_valeur, "statut": lot.statut,
         "nombre_ordres": lot.nombre_ordres, "total": lot.total, "nb_exclus": len(lot.exclus), "cree_par": lot.cree_par,
         "lance_par": lot.lance_par, "lance_le": lot.lance_le}
    if detail:
        d["exclus"] = lot.exclus
        d["ordres"] = [{"matricule": o.salarie.matricule, "nom": f"{o.salarie.nom} {o.salarie.prenoms or ''}".strip(),
                        "banque": o.banque, "montant": o.montant} for o in lot.ordres]
    return d


@router.get("/virements")
def lister(db: Session = Depends(get_db), _=Depends(GERER)):
    return [_sortie(l) for l in db.query(models.LotVirement).order_by(models.LotVirement.id.desc()).limit(200).all()]


@router.get("/virements/{lot_id}")
def detail(lot_id: int, db: Session = Depends(get_db), _=Depends(GERER)):
    return _sortie(_lot(db, lot_id), True)


@router.post("/campagnes/{campagne_id}/virements", status_code=201)
def preparer(campagne_id: int, corps: LotIn, request: Request, db: Session = Depends(get_db),
             acteur: models.Utilisateur = Depends(GERER)):
    c = db.get(models.Campagne, campagne_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Campagne introuvable.")
    try:
        lot = svc.preparer(db, c, acteur, corps.date_valeur)
    except ErreurPaie as e:
        db.rollback()
        raise HTTPException(status_code=e.statut, detail=str(e))
    audit.enregistrer(db, "virement_prepare", acteur=acteur, cible_type="lot_virement", cible_id=lot.id,
                      detail={"campagne": c.libelle, "ordres": lot.nombre_ordres, "total": str(lot.total), "exclus": len(lot.exclus)}, request=request)
    db.commit()
    return _sortie(lot, True)


@router.post("/virements/{lot_id}/annuler")
def annuler(lot_id: int, request: Request, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(GERER)):
    lot = _lot(db, lot_id)
    try:
        svc.annuler(db, lot)
    except ErreurPaie as e:
        raise HTTPException(status_code=e.statut, detail=str(e))
    audit.enregistrer(db, "virement_annule", acteur=acteur, cible_type="lot_virement", cible_id=lot.id, request=request)
    db.commit()
    return _sortie(lot)


@router.post("/virements/{lot_id}/lancer")
def lancer(lot_id: int, request: Request, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(GERER)):
    lot = _lot(db, lot_id)
    try:
        svc.lancer(db, lot, acteur)
    except ErreurPaie as e:
        raise HTTPException(status_code=e.statut, detail=str(e))
    audit.enregistrer(db, "virement_lance", acteur=acteur, cible_type="lot_virement", cible_id=lot.id,
                      detail={"ordres": lot.nombre_ordres, "total": str(lot.total)}, request=request)
    db.commit()
    try:                                  # l'alerte ne doit jamais empêcher ni défaire le virement
        messagerie.alerter_virement(db, lot, acteur)
    except Exception:
        db.rollback()
    return _sortie(lot)


@router.get("/virements/{lot_id}/fichier")
def fichier(lot_id: int, request: Request, format: str = Query(default="xlsx", pattern="^(xlsx|csv)$"),
            db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(GERER)):
    lot = _lot(db, lot_id)
    if lot.statut == "annule":
        raise HTTPException(status_code=409, detail="Ce lot est annulé.")
    c = db.get(models.Campagne, lot.campagne_id)
    entetes, lignes = svc.lignes_export(db, lot, c)
    audit.enregistrer(db, "virement_fichier_exporte", acteur=acteur, cible_type="lot_virement", cible_id=lot.id,
                      detail={"format": format, "ordres": len(lignes), "rib_en_clair": True}, request=request)
    db.commit()
    contenu = fichiers.xlsx("Virements", entetes, lignes, {"Montant (FCFA)": lot.total}, lot.libelle) if format == "xlsx" else fichiers.csv_fr(entetes, lignes)
    return Response(content=contenu, media_type=fichiers.MEDIA[format],
                    headers={"Content-Disposition": f'attachment; filename="virements_{lot.id}.{format}"'})
