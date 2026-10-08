"""Espace salarié : chacun ne voit que ses propres données (bulletins, congés, prêts)."""
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core import models
from ..core.database import get_db
from ..exports import bulletin_pdf
from ..services import audit
from ..services import conges as svc_conges
from ..services import prets as svc_prets
from .auth_routes import get_current_user

router = APIRouter(prefix="/moi", tags=["Espace salarié"])


def moi(db: Session = Depends(get_db), user: models.Utilisateur = Depends(get_current_user)) -> models.Salarie:
    """Le salarié rattaché au compte connecté (identifiant = matricule). Aucun autre accès possible."""
    s = db.query(models.Salarie).filter_by(matricule=user.identifiant).first() if user.role == "salarie" else None
    if s is None:
        raise HTTPException(status_code=403, detail="Cet espace est réservé aux salariés.")
    return s


def _ref(r):
    return None if r is None else r.libelle


@router.get("/profil")
def profil(s: models.Salarie = Depends(moi)):
    return {"matricule": s.matricule, "nom": s.nom, "prenoms": s.prenoms, "emploi": _ref(s.emploi), "service": _ref(s.service),
            "date_embauche": s.date_embauche, "email": s.email, "telephone": s.telephone, "mode_paiement": s.mode_paiement,
            "a_un_rib": bool(s.rib_chiffre)}


@router.get("/bulletins")
def mes_bulletins(db: Session = Depends(get_db), s: models.Salarie = Depends(moi)):
    lignes = db.query(models.Bulletin, models.Campagne).join(models.Campagne, models.Campagne.id == models.Bulletin.campagne_id)\
        .filter(models.Bulletin.salarie_id == s.id, models.Bulletin.statut == "valide")\
        .order_by(models.Campagne.annee.desc(), models.Campagne.mois.desc(), models.Campagne.numero.desc()).all()
    return [{"id": b.id, "libelle": c.libelle, "annee": c.annee, "mois": c.mois, "numero": c.numero, "debut": c.debut, "fin": c.fin,
             "net_a_payer": b.net_a_payer, "lu": b.lu_le is not None} for b, c in lignes]


def _mon_bulletin(db: Session, s: models.Salarie, bulletin_id: int) -> models.Bulletin:
    b = db.get(models.Bulletin, bulletin_id)
    # 404 (et non 403) pour ne pas révéler l'existence du bulletin d'un autre salarié
    if b is None or b.salarie_id != s.id or b.statut != "valide":
        raise HTTPException(status_code=404, detail="Bulletin introuvable.")
    return b


@router.get("/bulletins/{bulletin_id}")
def mon_bulletin(bulletin_id: int, db: Session = Depends(get_db), s: models.Salarie = Depends(moi)):
    b = _mon_bulletin(db, s, bulletin_id)
    c = db.get(models.Campagne, b.campagne_id)
    return {"id": b.id, "libelle": c.libelle, "debut": c.debut, "fin": c.fin, "lignes": b.lignes, "total_imposable": b.total_imposable,
            "cnps": b.cnps, "its": b.its, "total_impots": b.total_impots, "gains_non_imposables": b.gains_non_imposables,
            "retenues_non_imposables": b.retenues_non_imposables, "net_a_payer": b.net_a_payer}


@router.get("/bulletins/{bulletin_id}/pdf")
def mon_bulletin_pdf(bulletin_id: int, request: Request, db: Session = Depends(get_db), s: models.Salarie = Depends(moi),
                     user: models.Utilisateur = Depends(get_current_user)):
    b = _mon_bulletin(db, s, bulletin_id)
    c = db.get(models.Campagne, b.campagne_id)
    if b.lu_le is None:
        b.lu_le = datetime.now(timezone.utc)
    audit.enregistrer(db, "bulletin_consulte_par_salarie", acteur=user, cible_type="bulletin", cible_id=b.id, request=request)
    db.commit()
    return Response(content=bulletin_pdf.generer(db, c, [b]), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="bulletin_{c.annee}{c.mois:02d}_{c.numero}.pdf"'})


# ----------------------------------------------------------------- congés
class DemandeCongeIn(BaseModel):
    type_conge: str = Field(default="annuel", pattern="^(annuel|maladie|exceptionnel|sans_solde)$")
    debut: date
    fin: date
    motif: Optional[str] = Field(default=None, max_length=200)


@router.get("/conges")
def mes_conges(db: Session = Depends(get_db), s: models.Salarie = Depends(moi)):
    liste = db.query(models.Conge).filter_by(salarie_id=s.id).order_by(models.Conge.debut.desc()).limit(100).all()
    return {"solde": svc_conges.solde(db, s),
            "demandes": [{"id": c.id, "type_conge": c.type_conge, "debut": c.debut, "fin": c.fin, "jours_ouvrables": c.jours_ouvrables,
                          "statut": c.statut, "motif": c.motif} for c in liste]}


@router.post("/conges", status_code=201)
def demander_conge(corps: DemandeCongeIn, request: Request, db: Session = Depends(get_db), s: models.Salarie = Depends(moi),
                   user: models.Utilisateur = Depends(get_current_user)):
    if corps.fin < corps.debut:
        raise HTTPException(status_code=422, detail="La fin précède le début.")
    if corps.debut < date.today():
        raise HTTPException(status_code=422, detail="Une demande ne peut pas commencer dans le passé : contactez le service Paie.")
    if db.query(models.Conge).filter(models.Conge.salarie_id == s.id, models.Conge.statut.in_(("demande", "approuve")),
                                     models.Conge.debut <= corps.fin, models.Conge.fin >= corps.debut).first():
        raise HTTPException(status_code=409, detail="Ces dates chevauchent un autre congé.")
    c = models.Conge(salarie_id=s.id, type_conge=corps.type_conge, debut=corps.debut, fin=corps.fin, motif=corps.motif,
                     jours_ouvrables=svc_conges.jours_ouvrables(db, corps.debut, corps.fin), cree_par=user.identifiant)
    db.add(c)
    db.flush()
    audit.enregistrer(db, "conge_demande", acteur=user, cible_type="conge", cible_id=c.id, detail={"par_le_salarie": True}, request=request)
    db.commit()
    return {"id": c.id, "jours_ouvrables": c.jours_ouvrables, "statut": c.statut}


@router.delete("/conges/{conge_id}", status_code=204)
def annuler_ma_demande(conge_id: int, request: Request, db: Session = Depends(get_db), s: models.Salarie = Depends(moi),
                       user: models.Utilisateur = Depends(get_current_user)):
    c = db.get(models.Conge, conge_id)
    if c is None or c.salarie_id != s.id:
        raise HTTPException(status_code=404, detail="Demande introuvable.")
    if c.statut != "demande":
        raise HTTPException(status_code=409, detail="Seule une demande en attente peut être retirée.")
    c.statut, c.decide_par, c.decide_le = "annule", user.identifiant, datetime.now(timezone.utc)
    audit.enregistrer(db, "conge_annule", acteur=user, cible_type="conge", cible_id=c.id, detail={"par_le_salarie": True}, request=request)
    db.commit()


@router.get("/prets")
def mes_prets(db: Session = Depends(get_db), s: models.Salarie = Depends(moi)):
    prets = db.query(models.Pret).filter_by(salarie_id=s.id).order_by(models.Pret.id.desc()).all()
    return [{"libelle": p.libelle, "montant": p.montant, "statut": p.statut, "reste": svc_prets.reste_a_rembourser(p),
             "echeances": [{"annee": e.annee, "mois": e.mois, "montant": e.montant, "statut": e.statut} for e in p.echeances]} for p in prets]
