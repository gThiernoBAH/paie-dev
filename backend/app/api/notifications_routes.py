"""Envoi des bulletins par e-mail et suivi des notifications."""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core import models
from ..core.database import SessionLocal, get_db
from ..services import audit, messagerie
from .auth_routes import require_any_permission, require_permission

router = APIRouter(tags=["Notifications"])


class EnvoiIn(BaseModel):
    renvoyer: bool = False


class TestIn(BaseModel):
    destinataire: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=200)


def _traiter_en_arriere_plan(campagne_id: int) -> None:
    db = SessionLocal()
    try:
        messagerie.traiter_en_attente(db, campagne_id)
    finally:
        db.close()


def _sortie(n: models.Notification) -> dict:
    return {"id": n.id, "type": n.type_notif, "destinataire": n.destinataire, "objet": n.objet, "statut": n.statut, "erreur": n.erreur,
            "tentatives": n.tentatives, "campagne_id": n.campagne_id, "bulletin_id": n.bulletin_id, "cree_le": n.cree_le, "envoye_le": n.envoye_le}


@router.post("/campagnes/{campagne_id}/envoyer-bulletins", status_code=202)
def envoyer_bulletins(campagne_id: int, corps: EnvoiIn, tache: BackgroundTasks, request: Request, db: Session = Depends(get_db),
                      acteur: models.Utilisateur = Depends(require_permission("valider_bulletins"))):
    c = db.get(models.Campagne, campagne_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Campagne introuvable.")
    if c.statut not in ("validee", "cloturee"):
        raise HTTPException(status_code=409, detail="Les bulletins ne peuvent être envoyés qu'une fois la campagne validée.")
    resume = messagerie.preparer_envoi_bulletins(db, c, acteur, corps.renvoyer)
    audit.enregistrer(db, "bulletins_envoi_demande", acteur=acteur, cible_type="campagne", cible_id=c.id, detail=resume, request=request)
    db.commit()
    if resume["en_attente"]:
        tache.add_task(_traiter_en_arriere_plan, c.id)
    return resume


@router.post("/campagnes/{campagne_id}/relancer-envois", status_code=202)
def relancer(campagne_id: int, tache: BackgroundTasks, db: Session = Depends(get_db),
             acteur: models.Utilisateur = Depends(require_permission("valider_bulletins"))):
    n = 0
    for notif in db.query(models.Notification).filter_by(campagne_id=campagne_id, type_notif="bulletin").filter(
            models.Notification.statut.in_(("echec", "desactive"))).all():
        messagerie.renvoyer(db, notif)
        n += 1
    db.commit()
    if n:
        tache.add_task(_traiter_en_arriere_plan, campagne_id)
    return {"relances": n}


@router.get("/notifications")
def lister(campagne_id: Optional[int] = None, statut: Optional[str] = None, limite: int = Query(default=300, le=2000),
           db: Session = Depends(get_db), _=Depends(require_any_permission("lancer_paie", "valider_bulletins", "gerer_virements"))):
    q = db.query(models.Notification)
    if campagne_id:
        q = q.filter(models.Notification.campagne_id == campagne_id)
    if statut:
        q = q.filter(models.Notification.statut == statut)
    return [_sortie(n) for n in q.order_by(models.Notification.id.desc()).limit(limite).all()]


@router.get("/campagnes/{campagne_id}/envois")
def resume_envois(campagne_id: int, db: Session = Depends(get_db),
                  _=Depends(require_any_permission("lancer_paie", "valider_bulletins"))):
    from sqlalchemy import func
    lignes = db.query(models.Notification.statut, func.count()).filter_by(campagne_id=campagne_id, type_notif="bulletin")\
        .group_by(models.Notification.statut).all()
    return {statut: n for statut, n in lignes}


@router.post("/email/test")
def tester(corps: TestIn, request: Request, db: Session = Depends(get_db),
           acteur: models.Utilisateur = Depends(require_permission("gerer_parametres"))):
    n = messagerie.envoyer_test(db, corps.destinataire, acteur)
    audit.enregistrer(db, "email_test", acteur=acteur, cible_type="notification", cible_id=n.id, detail={"statut": n.statut}, request=request)
    db.commit()
    return _sortie(n)
