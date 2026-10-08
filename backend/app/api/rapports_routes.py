"""Rapports de pilotage et tableau de bord."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core import models
from ..core.database import get_db
from ..services import audit, rapports
from ..services import parametres as param
from .auth_routes import a_la_permission, get_current_user, require_permission
from .declarations_routes import _reponse

router = APIRouter(tags=["Rapports"])
VOIR = require_permission("voir_rapports")
FORMAT = Query(default="json", pattern="^(json|xlsx|csv)$")


@router.get("/rapports/masse-salariale")
def masse_salariale(annee: int = Query(ge=2000, le=2100), format: str = FORMAT, db: Session = Depends(get_db), _=Depends(VOIR)):
    r = rapports.masse_salariale(db, annee)
    return _reponse(r["titre"], r["entetes"], r["lignes"], r["totaux"], format)


@router.get("/rapports/par-service")
def par_service(annee: int = Query(ge=2000, le=2100), mois: int = Query(ge=1, le=12), format: str = FORMAT, db: Session = Depends(get_db), _=Depends(VOIR)):
    r = rapports.par_service(db, annee, mois)
    return _reponse(r["titre"], r["entetes"], r["lignes"], r["totaux"], format)


@router.get("/rapports/heures-supplementaires")
def heures_sup(annee: int = Query(ge=2000, le=2100), format: str = FORMAT, db: Session = Depends(get_db), _=Depends(VOIR)):
    r = rapports.heures_supplementaires(db, annee)
    return _reponse(r["titre"], r["entetes"], r["lignes"], r["totaux"], format)


@router.get("/rapports/effectif")
def effectif(au: Optional[date] = None, format: str = FORMAT, db: Session = Depends(get_db), _=Depends(VOIR)):
    r = rapports.effectif(db, au)
    return _reponse(r["titre"], r["entetes"], r["lignes"], r["totaux"], format)


@router.get("/rapports/mouvements")
def mouvements(du: date, au: date, format: str = FORMAT, db: Session = Depends(get_db), _=Depends(VOIR)):
    if au < du:
        raise HTTPException(status_code=422, detail="La fin précède le début.")
    r = rapports.mouvements(db, du, au)
    return _reponse(r["titre"], r["entetes"], r["lignes"], r["totaux"], format)


@router.get("/rapports/livre-de-paie")
def livre_de_paie(request: Request, annee: int = Query(ge=2000, le=2100), mois: int = Query(ge=1, le=12), format: str = FORMAT,
                  db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(VOIR)):
    """Nominatif : exige en plus le droit sur les données sensibles ; l'accès est tracé."""
    if not a_la_permission(acteur, "voir_donnees_sensibles"):
        raise HTTPException(status_code=403, detail="Permission manquante : voir_donnees_sensibles")
    r = rapports.livre_de_paie(db, annee, mois)
    audit.enregistrer(db, "livre_de_paie_consulte", acteur=acteur, cible_type="rapport", cible_id=f"{annee}-{mois:02d}",
                      detail={"format": format, "lignes": len(r["lignes"]), "donnees_sensibles": True}, request=request)
    db.commit()
    return _reponse(r["titre"], r["entetes"], r["lignes"], r["totaux"], format)


@router.get("/tableau-de-bord")
def tableau_de_bord(db: Session = Depends(get_db), u: models.Utilisateur = Depends(get_current_user)):
    """Indicateurs et points d'attention, limités à ce que les droits du compte permettent de voir."""
    if u.role == "salarie":
        raise HTTPException(status_code=403, detail="Réservé aux gestionnaires.")
    out: dict = {"effectif_actif": None, "derniere_paie": None, "campagne_en_cours": None, "a_traiter": {}}
    if a_la_permission(u, "voir_salaries"):
        out["effectif_actif"] = db.query(models.Salarie).filter(models.Salarie.est_actif.is_(True)).count()
    if a_la_permission(u, "voir_rapports") or a_la_permission(u, "lancer_paie"):
        c = db.query(models.Campagne).filter(models.Campagne.statut.in_(("validee", "cloturee"))).order_by(
            models.Campagne.annee.desc(), models.Campagne.mois.desc(), models.Campagne.numero.desc()).first()
        if c and a_la_permission(u, "voir_rapports"):
            agg = db.query(func.count(models.Bulletin.id), func.coalesce(func.sum(models.Bulletin.net_a_payer), 0)).filter_by(campagne_id=c.id).one()
            out["derniere_paie"] = {"campagne_id": c.id, "libelle": c.libelle, "bulletins": agg[0], "net": agg[1]}
        en_cours = db.query(models.Campagne).filter(models.Campagne.statut.in_(("ouverte", "calculee"))).order_by(models.Campagne.id.desc()).first()
        if en_cours:
            out["campagne_en_cours"] = {"campagne_id": en_cours.id, "libelle": en_cours.libelle, "statut": en_cours.statut}
    a = out["a_traiter"]
    if a_la_permission(u, "gerer_conges"):
        a["conges_en_attente"] = db.query(models.Conge).filter_by(statut="demande").count()
    if a_la_permission(u, "gerer_virements"):
        a["virements_a_lancer"] = db.query(models.LotVirement).filter_by(statut="prepare").count()
    if a_la_permission(u, "valider_bulletins"):
        a["envois_en_echec"] = db.query(models.Notification).filter_by(type_notif="bulletin", statut="echec").count()
    if a_la_permission(u, "voir_parametres"):
        a["parametres_critiques_a_confirmer"] = len(param.critiques_a_confirmer(db, date.today()))
    return out
