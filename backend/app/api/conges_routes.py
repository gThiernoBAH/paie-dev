"""Congés, prêts et avances, soldes de tout compte."""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core import models
from ..core.database import get_db
from ..services import audit
from ..services import conges as svc_conges
from ..services import prets as svc_prets
from ..services import soldes as svc_soldes
from ..services.bulletins import ErreurPaie
from .auth_routes import require_permission

router = APIRouter(tags=["Congés, prêts, soldes"])
GERER = require_permission("gerer_conges")


def _salarie(db: Session, sid: int) -> models.Salarie:
    s = db.get(models.Salarie, sid)
    if s is None:
        raise HTTPException(status_code=404, detail="Salarié introuvable.")
    return s


def _nom(s: models.Salarie) -> str:
    return f"{s.nom} {s.prenoms or ''}".strip()


# ----------------------------------------------------------------- congés
class CongeIn(BaseModel):
    salarie_id: int
    type_conge: str = Field(default="annuel", pattern="^(annuel|maladie|maternite|exceptionnel|sans_solde)$")
    debut: date
    fin: date
    motif: Optional[str] = Field(default=None, max_length=200)


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(approuver|refuser|annuler)$")


class SoldeInitialIn(BaseModel):
    solde_initial: Decimal = Field(ge=0, le=500)
    date_reference: date


def _conge_sortie(c: models.Conge) -> dict:
    return {"id": c.id, "salarie_id": c.salarie_id, "matricule": c.salarie.matricule, "nom": _nom(c.salarie),
            "type_conge": c.type_conge, "debut": c.debut, "fin": c.fin, "jours_ouvrables": c.jours_ouvrables,
            "statut": c.statut, "motif": c.motif, "decide_par": c.decide_par}


@router.get("/conges")
def lister_conges(statut: Optional[str] = None, salarie_id: Optional[int] = None, limite: int = Query(default=300, le=1000),
                  db: Session = Depends(get_db), _=Depends(GERER)):
    q = db.query(models.Conge)
    if statut:
        q = q.filter(models.Conge.statut == statut)
    if salarie_id:
        q = q.filter(models.Conge.salarie_id == salarie_id)
    return [_conge_sortie(c) for c in q.order_by(models.Conge.debut.desc()).limit(limite).all()]


@router.post("/conges", status_code=201)
def demander_conge(corps: CongeIn, request: Request, db: Session = Depends(get_db),
                   acteur: models.Utilisateur = Depends(GERER)):
    s = _salarie(db, corps.salarie_id)
    if corps.fin < corps.debut:
        raise HTTPException(status_code=422, detail="La fin précède le début.")
    jours = svc_conges.jours_ouvrables(db, corps.debut, corps.fin)
    chevauche = db.query(models.Conge).filter(
        models.Conge.salarie_id == s.id, models.Conge.statut.in_(("demande", "approuve")),
        models.Conge.debut <= corps.fin, models.Conge.fin >= corps.debut).first()
    if chevauche:
        raise HTTPException(status_code=409, detail="Ces dates chevauchent un autre congé du salarié.")
    c = models.Conge(salarie_id=s.id, type_conge=corps.type_conge, debut=corps.debut, fin=corps.fin,
                     jours_ouvrables=jours, motif=corps.motif, cree_par=acteur.identifiant)
    db.add(c)
    db.flush()
    audit.enregistrer(db, "conge_demande", acteur=acteur, cible_type="conge", cible_id=c.id,
                      detail={"matricule": s.matricule, "debut": corps.debut.isoformat(), "fin": corps.fin.isoformat()}, request=request)
    db.commit()
    db.refresh(c)
    return _conge_sortie(c)


@router.post("/conges/{conge_id}/decision")
def decider_conge(conge_id: int, corps: DecisionIn, request: Request, db: Session = Depends(get_db),
                  acteur: models.Utilisateur = Depends(GERER)):
    c = db.get(models.Conge, conge_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Congé introuvable.")
    if corps.decision == "annuler":
        if c.statut not in ("demande", "approuve"):
            raise HTTPException(status_code=409, detail="Ce congé ne peut pas être annulé.")
        c.statut = "annule"
    else:
        if c.statut != "demande":
            raise HTTPException(status_code=409, detail="Ce congé a déjà fait l'objet d'une décision.")
        if corps.decision == "approuver" and c.type_conge == "annuel":
            solde = svc_conges.solde(db, c.salarie, c.debut)["solde"]
            if c.jours_ouvrables > solde:
                raise HTTPException(status_code=409, detail=f"Solde insuffisant : {solde} jour(s) disponible(s) pour {c.jours_ouvrables} demandé(s).")
        c.statut = "approuve" if corps.decision == "approuver" else "refuse"
    c.decide_par, c.decide_le = acteur.identifiant, datetime.now(timezone.utc)
    audit.enregistrer(db, "conge_" + c.statut, acteur=acteur, cible_type="conge", cible_id=c.id,
                      detail={"matricule": c.salarie.matricule}, request=request)
    db.commit()
    return _conge_sortie(c)


@router.get("/conges/soldes")
def soldes_conges(recherche: Optional[str] = None, db: Session = Depends(get_db), _=Depends(GERER)):
    q = db.query(models.Salarie).filter(models.Salarie.est_actif.is_(True))
    if recherche:
        motif = f"%{recherche.strip().lower()}%"
        q = q.filter(models.Salarie.matricule.like(motif) | models.Salarie.nom.ilike(motif))
    out = []
    for s in q.order_by(models.Salarie.matricule).limit(1000).all():
        out.append({"salarie_id": s.id, "matricule": s.matricule, "nom": _nom(s), **svc_conges.solde(db, s)})
    return out


@router.put("/salaries/{salarie_id}/solde-conges")
def definir_solde_initial(salarie_id: int, corps: SoldeInitialIn, request: Request, db: Session = Depends(get_db),
                          acteur: models.Utilisateur = Depends(GERER)):
    s = _salarie(db, salarie_id)
    avant = {"solde": str(s.solde_conges_initial), "date": str(s.solde_conges_date)}
    s.solde_conges_initial, s.solde_conges_date = corps.solde_initial, corps.date_reference
    audit.enregistrer(db, "solde_conges_defini", acteur=acteur, cible_type="salarie", cible_id=s.id,
                      detail={"avant": avant, "apres": {"solde": str(corps.solde_initial), "date": corps.date_reference.isoformat()}}, request=request)
    db.commit()
    return svc_conges.solde(db, s)


# ----------------------------------------------------------------- prêts et avances
class PretIn(BaseModel):
    salarie_id: int
    type_pret: str = Field(default="pret", pattern="^(pret|avance)$")
    libelle: str = Field(min_length=2, max_length=100)
    montant: Decimal = Field(gt=0, le=Decimal("1000000000"))
    nombre_echeances: int = Field(ge=1, le=120)
    annee_debut: int = Field(ge=2000, le=2100)
    mois_debut: int = Field(ge=1, le=12)


class ReglementIn(BaseModel):
    date_reglement: date
    mode_reglement: str = Field(default="especes", pattern="^(especes|cheque|virement|autre)$")
    commentaire: Optional[str] = Field(default=None, max_length=200)


class ClotureIn(BaseModel):
    motif: str = Field(pattern="^(depart|demission|deces|licenciement|autre)$")
    issue: str = Field(pattern="^(regularise|abandon)$")
    date_cloture: date
    commentaire: Optional[str] = Field(default=None, max_length=300)


def _pret_sortie(p: models.Pret, detail: bool = False, db: Optional[Session] = None) -> dict:
    nb_reglees = sum(1 for e in p.echeances if e.statut in ("prelevee", "reglee"))
    d = {"id": p.id, "salarie_id": p.salarie_id, "matricule": p.salarie.matricule, "nom": _nom(p.salarie), "type_pret": p.type_pret,
         "libelle": p.libelle, "montant": p.montant, "nombre_echeances": p.nombre_echeances, "statut": p.statut,
         "reste": svc_prets.reste_a_rembourser(p), "regle": svc_prets.montant_regle(p), "abandonne": svc_prets.montant_abandonne(p),
         "echeances_reglees": nb_reglees, "motif_cloture": p.motif_cloture, "issue_cloture": p.issue_cloture,
         "date_cloture": p.date_cloture, "commentaire_cloture": p.commentaire_cloture}
    if detail:
        libelles = {}
        if db is not None:
            ids = {e.campagne_id for e in p.echeances if e.campagne_id}
            libelles = {c.id: c.libelle for c in db.query(models.Campagne).filter(models.Campagne.id.in_(ids or {0})).all()}
        d["echeances"] = [{"id": e.id, "annee": e.annee, "mois": e.mois, "montant": e.montant, "statut": e.statut,
                           "date_reglement": e.date_reglement, "mode_reglement": e.mode_reglement, "commentaire": e.commentaire,
                           "campagne": libelles.get(e.campagne_id)} for e in p.echeances]
    return d


@router.get("/prets")
def lister_prets(statut: Optional[str] = None, db: Session = Depends(get_db), _=Depends(GERER)):
    q = db.query(models.Pret)
    if statut:
        q = q.filter(models.Pret.statut == statut)
    return [_pret_sortie(p) for p in q.order_by(models.Pret.id.desc()).limit(500).all()]


@router.post("/prets", status_code=201)
def creer_pret(corps: PretIn, request: Request, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(GERER)):
    s = _salarie(db, corps.salarie_id)
    p = svc_prets.creer(db, s, corps.type_pret, corps.libelle.strip(), corps.montant, corps.nombre_echeances,
                        corps.annee_debut, corps.mois_debut, acteur)
    audit.enregistrer(db, "pret_cree", acteur=acteur, cible_type="pret", cible_id=p.id,
                      detail={"matricule": s.matricule, "montant": str(corps.montant), "echeances": corps.nombre_echeances}, request=request)
    db.commit()
    db.refresh(p)
    return _pret_sortie(p, True, db)


@router.get("/prets/{pret_id}")
def detail_pret(pret_id: int, db: Session = Depends(get_db), _=Depends(GERER)):
    p = db.get(models.Pret, pret_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Prêt introuvable.")
    return _pret_sortie(p, True, db)


@router.post("/prets/{pret_id}/annuler")
def annuler_pret(pret_id: int, request: Request, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(GERER)):
    p = db.get(models.Pret, pret_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Prêt introuvable.")
    if p.statut != "actif":
        raise HTTPException(status_code=409, detail="Seul un prêt actif peut être annulé.")
    svc_prets.annuler(db, p)
    audit.enregistrer(db, "pret_annule", acteur=acteur, cible_type="pret", cible_id=p.id, request=request)
    db.commit()
    return _pret_sortie(p, True, db)


def _pret(db: Session, pret_id: int) -> models.Pret:
    p = db.get(models.Pret, pret_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Prêt introuvable.")
    return p


@router.post("/prets/{pret_id}/echeances/{echeance_id}/regler")
def regler_echeance(pret_id: int, echeance_id: int, corps: ReglementIn, request: Request, db: Session = Depends(get_db),
                    acteur: models.Utilisateur = Depends(GERER)):
    p = _pret(db, pret_id)
    e = db.get(models.EcheancePret, echeance_id)
    if e is None or e.pret_id != p.id:
        raise HTTPException(status_code=404, detail="Échéance introuvable.")
    try:
        a_recalculer = svc_prets.regler_echeance(db, p, e, corps.date_reglement, corps.mode_reglement, corps.commentaire, acteur)
    except svc_prets.ErreurPret as err:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(err))
    audit.enregistrer(db, "pret_echeance_reglee", acteur=acteur, cible_type="pret", cible_id=p.id,
                      detail={"echeance": f"{e.mois:02d}/{e.annee}", "montant": str(e.montant), "mode": corps.mode_reglement,
                              "date": corps.date_reglement.isoformat()}, request=request)
    db.commit()
    out = _pret_sortie(p, True, db)
    out["campagnes_a_recalculer"] = a_recalculer
    return out


@router.post("/prets/{pret_id}/echeances/{echeance_id}/rouvrir")
def rouvrir_echeance(pret_id: int, echeance_id: int, request: Request, db: Session = Depends(get_db),
                     acteur: models.Utilisateur = Depends(GERER)):
    p = _pret(db, pret_id)
    e = db.get(models.EcheancePret, echeance_id)
    if e is None or e.pret_id != p.id:
        raise HTTPException(status_code=404, detail="Échéance introuvable.")
    try:
        svc_prets.rouvrir_echeance(db, p, e)
    except svc_prets.ErreurPret as err:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(err))
    audit.enregistrer(db, "pret_reglement_annule", acteur=acteur, cible_type="pret", cible_id=p.id,
                      detail={"echeance": f"{e.mois:02d}/{e.annee}", "montant": str(e.montant)}, request=request)
    db.commit()
    return _pret_sortie(p, True, db)


@router.post("/prets/{pret_id}/cloturer")
def cloturer_pret(pret_id: int, corps: ClotureIn, request: Request, db: Session = Depends(get_db),
                  acteur: models.Utilisateur = Depends(GERER)):
    """Clôture anticipée : départ surprise, démission, décès… Le reste dû est régularisé hors paie ou passé en perte."""
    p = _pret(db, pret_id)
    reste = svc_prets.reste_a_rembourser(p)
    try:
        a_recalculer = svc_prets.cloturer(db, p, corps.motif, corps.issue, corps.date_cloture, corps.commentaire, acteur)
    except svc_prets.ErreurPret as err:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(err))
    audit.enregistrer(db, "pret_cloture", acteur=acteur, cible_type="pret", cible_id=p.id,
                      detail={"motif": corps.motif, "issue": corps.issue, "reste": str(reste), "date": corps.date_cloture.isoformat()},
                      request=request)
    db.commit()
    out = _pret_sortie(p, True, db)
    out["campagnes_a_recalculer"] = a_recalculer
    return out


# ----------------------------------------------------------------- solde de tout compte
class SoldeIn(BaseModel):
    salarie_id: int
    date_sortie: date
    motif: str
    jours_conges: Optional[Decimal] = Field(default=None, ge=0, le=500)
    preavis: Optional[Decimal] = Field(default=None, ge=0, le=Decimal("1000000000"))


@router.get("/soldes/apercu")
def apercu_solde(salarie_id: int, date_sortie: date, motif: str, db: Session = Depends(get_db), _=Depends(GERER)):
    s = _salarie(db, salarie_id)
    if motif not in svc_soldes.MOTIFS:
        raise HTTPException(status_code=422, detail="Motif de sortie inconnu.")
    try:
        return svc_soldes.apercu(db, s, date_sortie, motif)
    except ErreurPaie as e:
        raise HTTPException(status_code=e.statut, detail=str(e))


@router.get("/soldes/motifs")
def motifs(_=Depends(GERER)):
    return [{"cle": k, "libelle": v} for k, v in svc_soldes.MOTIFS.items()]


@router.post("/soldes", status_code=201)
def creer_solde(corps: SoldeIn, request: Request, db: Session = Depends(get_db),
                acteur: models.Utilisateur = Depends(GERER)):
    s = _salarie(db, corps.salarie_id)
    try:
        c = svc_soldes.creer(db, s, corps.date_sortie, corps.motif, acteur, corps.jours_conges, corps.preavis)
    except ErreurPaie as e:
        db.rollback()
        raise HTTPException(status_code=e.statut, detail=str(e))
    audit.enregistrer(db, "solde_tout_compte_cree", acteur=acteur, cible_type="campagne", cible_id=c.id,
                      detail={"matricule": s.matricule, "motif": corps.motif, "date": corps.date_sortie.isoformat()}, request=request)
    db.commit()
    return {"campagne_id": c.id, "libelle": c.libelle}
