"""Rapports de pilotage et tableau de bord."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core import models
from ..core.database import get_db
from ..services import audit, rapports
from ..services import grille as svc_grille
from ..services import statistiques as stats
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


@router.get("/rapports/liste-personnel")
def liste_personnel(au: Optional[date] = None, inclure_sortis: bool = False, format: str = FORMAT, db: Session = Depends(get_db), _=Depends(VOIR)):
    r = rapports.liste_personnel(db, au, inclure_sortis)
    return _reponse(r["titre"], r["entetes"], r["lignes"], r["totaux"], format)


@router.get("/rapports/situation-famille")
def situation_famille(au: Optional[date] = None, format: str = FORMAT, db: Session = Depends(get_db), _=Depends(VOIR)):
    r = rapports.situation_famille(db, au)
    return _reponse(r["titre"], r["entetes"], r["lignes"], r["totaux"], format)


@router.get("/rapports/journal-presences")
def journal_presences(annee: int = Query(ge=2000, le=2100), mois: int = Query(ge=1, le=12), format: str = FORMAT, db: Session = Depends(get_db), _=Depends(VOIR)):
    r = rapports.journal_presences(db, annee, mois)
    return _reponse(r["titre"], r["entetes"], r["lignes"], r["totaux"], format)


@router.get("/rapports/journal-conges")
def journal_conges(annee: int = Query(ge=2000, le=2100), format: str = FORMAT, db: Session = Depends(get_db), _=Depends(VOIR)):
    r = rapports.journal_conges(db, annee)
    return _reponse(r["titre"], r["entetes"], r["lignes"], r["totaux"], format)


def _nominatif(request: Request, db: Session, acteur: models.Utilisateur, nom: str, cible: str, r: dict, format: str):
    """Rapports nominatifs avec montants : droit « données sensibles » exigé, consultation tracée."""
    if not a_la_permission(acteur, "voir_donnees_sensibles"):
        raise HTTPException(status_code=403, detail="Permission manquante : voir_donnees_sensibles")
    audit.enregistrer(db, f"{nom}_consulte", acteur=acteur, cible_type="rapport", cible_id=cible,
                      detail={"format": format, "lignes": len(r["lignes"]), "donnees_sensibles": True}, request=request)
    db.commit()
    return _reponse(r["titre"], r["entetes"], r["lignes"], r["totaux"], format)


@router.get("/rapports/journal-rubriques")
def journal_rubriques(request: Request, annee: int = Query(ge=2000, le=2100), mois: int = Query(ge=1, le=12), format: str = FORMAT,
                      db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(VOIR)):
    return _nominatif(request, db, acteur, "journal_rubriques", f"{annee}-{mois:02d}", rapports.journal_rubriques(db, annee, mois), format)


@router.get("/rapports/journal-prets")
def journal_prets(request: Request, format: str = FORMAT, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(VOIR)):
    return _nominatif(request, db, acteur, "journal_prets", "prets", rapports.journal_prets(db), format)


@router.get("/rapports/bulletins-a-controler")
def bulletins_a_controler(request: Request, annee: int = Query(ge=2000, le=2100), mois: int = Query(ge=1, le=12), format: str = FORMAT,
                          db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(VOIR)):
    return _nominatif(request, db, acteur, "bulletins_a_controler", f"{annee}-{mois:02d}", rapports.bulletins_a_controler(db, annee, mois), format)


@router.get("/rapports/hors-grille")
def hors_grille(request: Request, au: Optional[date] = None, format: str = FORMAT, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(VOIR)):
    return _nominatif(request, db, acteur, "hors_grille", str(au or date.today()), svc_grille.rapport_hors_grille(db, au), format)


@router.get("/rapports/cumuls-annuels")
def cumuls_annuels(request: Request, annee: int = Query(ge=2000, le=2100), format: str = FORMAT,
                   db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(VOIR)):
    return _nominatif(request, db, acteur, "cumuls_annuels", str(annee), rapports.cumuls_annuels(db, annee), format)


@router.get("/tableau-de-bord/statistiques")
def statistiques(annee: int = Query(default=None, ge=2000, le=2100), service_id: Optional[int] = None, db: Session = Depends(get_db),
                 u: models.Utilisateur = Depends(get_current_user)):
    """Séries prêtes pour les graphiques. Chaque bloc n'est livré que si les droits du compte le permettent :
    effectifs (voir_salaries), masse salariale réalisée et prévisionnel (voir_rapports)."""
    if u.role == "salarie":
        raise HTTPException(status_code=403, detail="Réservé aux gestionnaires.")
    annee = annee or date.today().year
    out: dict = {"annee": annee, "service_id": service_id, "effectifs": None, "masse": None, "previsionnel": None, "services": []}
    if a_la_permission(u, "voir_salaries"):
        out["effectifs"] = stats.effectifs(db, annee, service_id)
        out["services"] = [{"id": r.id, "libelle": r.libelle} for r in db.query(models.Referentiel)
                           .filter_by(type_ref="service", est_actif=True).order_by(models.Referentiel.libelle).all()]
    if a_la_permission(u, "voir_rapports"):
        out["masse"] = stats.masse(db, annee, service_id)
        out["previsionnel"] = stats.previsionnel(db, service_id)
    if out["effectifs"] is None and out["masse"] is None:
        raise HTTPException(status_code=403, detail="Permission manquante : voir_salaries ou voir_rapports.")
    return out


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
