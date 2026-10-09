"""Dossier du salarié : personnes à charge, rubriques fixes, vue d'ensemble (bulletins, congés, prêts, sanctions)."""
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core import models
from ..core.database import get_db
from ..services import audit
from ..services import conges as svc_conges
from ..services import prets as svc_prets
from ..services import rubriques_fixes as svc_fixes
from ..services import salaries as svc_salaries
from .auth_routes import a_la_permission, require_permission

router = APIRouter(prefix="/salaries", tags=["Dossier salarié"])
VOIR = require_permission("voir_salaries")
MODIFIER = require_permission("modifier_salaries")
SENSIBLE = require_permission("voir_donnees_sensibles")


def _salarie(db: Session, sid: int) -> models.Salarie:
    s = db.get(models.Salarie, sid)
    if s is None:
        raise HTTPException(status_code=404, detail="Salarié introuvable.")
    return s


# ----------------------------------------------------------------- personnes à charge
class EnfantIn(BaseModel):
    lien: str = Field(default="enfant", pattern="^(enfant|conjoint)$")
    nom: str = Field(min_length=1, max_length=100)
    prenoms: Optional[str] = Field(default=None, max_length=150)
    sexe: Optional[str] = Field(default=None, pattern="^[MF]$")
    date_naissance: Optional[date] = None
    a_charge: bool = True
    scolarise: bool = False


class EnfantMaj(BaseModel):
    lien: Optional[str] = Field(default=None, pattern="^(enfant|conjoint)$")
    nom: Optional[str] = Field(default=None, min_length=1, max_length=100)
    prenoms: Optional[str] = Field(default=None, max_length=150)
    sexe: Optional[str] = Field(default=None, pattern="^[MF]$")
    date_naissance: Optional[date] = None
    a_charge: Optional[bool] = None
    scolarise: Optional[bool] = None


def _age(n: Optional[date]) -> Optional[int]:
    if n is None:
        return None
    t = date.today()
    return t.year - n.year - ((t.month, t.day) < (n.month, n.day))


def _enfant_sortie(e: models.EnfantSalarie) -> dict:
    return {"id": e.id, "lien": e.lien, "nom": e.nom, "prenoms": e.prenoms, "sexe": e.sexe, "date_naissance": e.date_naissance,
            "age": _age(e.date_naissance), "a_charge": e.a_charge, "scolarise": e.scolarise}


def _synchroniser(db: Session, s: models.Salarie) -> dict:
    """Le compteur « enfants » de la fiche suit le détail ; les parts fiscales restent inchangées (proposition affichée)."""
    db.flush()
    nb = db.query(models.EnfantSalarie).filter_by(salarie_id=s.id, lien="enfant", a_charge=True).count()
    s.nombre_enfants = nb
    db.flush()
    suggerees = svc_salaries.parts_suggerees(s.situation_matrimoniale, nb)
    return {"nombre_enfants": nb, "parts_actuelles": float(s.nombre_parts), "parts_suggerees": float(suggerees)}


def _liste_enfants(db: Session, s: models.Salarie) -> dict:
    lignes = db.query(models.EnfantSalarie).filter_by(salarie_id=s.id).order_by(models.EnfantSalarie.date_naissance, models.EnfantSalarie.id).all()
    suggerees = svc_salaries.parts_suggerees(s.situation_matrimoniale, s.nombre_enfants)
    return {"elements": [_enfant_sortie(e) for e in lignes], "nombre_enfants": s.nombre_enfants,
            "parts_actuelles": float(s.nombre_parts), "parts_suggerees": float(suggerees)}


@router.get("/{salarie_id}/enfants")
def lister_enfants(salarie_id: int, db: Session = Depends(get_db), _=Depends(VOIR)):
    return _liste_enfants(db, _salarie(db, salarie_id))


@router.post("/{salarie_id}/enfants", status_code=201)
def ajouter_enfant(salarie_id: int, corps: EnfantIn, request: Request, db: Session = Depends(get_db),
                   acteur: models.Utilisateur = Depends(MODIFIER)):
    s = _salarie(db, salarie_id)
    if corps.date_naissance and corps.date_naissance > date.today():
        raise HTTPException(status_code=422, detail="La date de naissance est dans le futur.")
    e = models.EnfantSalarie(salarie_id=s.id, **corps.model_dump())
    db.add(e)
    _synchroniser(db, s)
    audit.enregistrer(db, "enfant_ajoute", acteur=acteur, cible_type="salarie", cible_id=s.id,
                      detail={"matricule": s.matricule, "lien": corps.lien}, request=request)
    db.commit()
    return _liste_enfants(db, s)


@router.patch("/{salarie_id}/enfants/{enfant_id}")
def modifier_enfant(salarie_id: int, enfant_id: int, corps: EnfantMaj, request: Request, db: Session = Depends(get_db),
                    acteur: models.Utilisateur = Depends(MODIFIER)):
    s = _salarie(db, salarie_id)
    e = db.get(models.EnfantSalarie, enfant_id)
    if e is None or e.salarie_id != s.id:
        raise HTTPException(status_code=404, detail="Personne à charge introuvable.")
    for k, v in corps.model_dump(exclude_unset=True).items():
        setattr(e, k, v)
    _synchroniser(db, s)
    audit.enregistrer(db, "enfant_modifie", acteur=acteur, cible_type="salarie", cible_id=s.id,
                      detail={"matricule": s.matricule}, request=request)
    db.commit()
    return _liste_enfants(db, s)


@router.delete("/{salarie_id}/enfants/{enfant_id}")
def supprimer_enfant(salarie_id: int, enfant_id: int, request: Request, db: Session = Depends(get_db),
                     acteur: models.Utilisateur = Depends(MODIFIER)):
    s = _salarie(db, salarie_id)
    e = db.get(models.EnfantSalarie, enfant_id)
    if e is None or e.salarie_id != s.id:
        raise HTTPException(status_code=404, detail="Personne à charge introuvable.")
    db.delete(e)
    _synchroniser(db, s)
    audit.enregistrer(db, "enfant_supprime", acteur=acteur, cible_type="salarie", cible_id=s.id,
                      detail={"matricule": s.matricule}, request=request)
    db.commit()
    return _liste_enfants(db, s)


# ----------------------------------------------------------------- rubriques fixes
class RubriqueFixeIn(BaseModel):
    code: str = Field(min_length=1, max_length=6)
    montant: Decimal = Field(gt=0, le=Decimal("1000000000"))
    date_debut: date
    date_fin: Optional[date] = None
    commentaire: Optional[str] = Field(default=None, max_length=200)


def _fixe_sortie(f: models.RubriqueFixe) -> dict:
    return {"id": f.id, "code": f.code, "libelle": f.rubrique.libelle, "type": f.rubrique.type, "montant": f.montant,
            "date_debut": f.date_debut, "date_fin": f.date_fin, "commentaire": f.commentaire, "est_actif": f.est_actif}


@router.get("/{salarie_id}/rubriques-fixes")
def lister_fixes(salarie_id: int, db: Session = Depends(get_db), _=Depends(SENSIBLE)):
    s = _salarie(db, salarie_id)
    lignes = db.query(models.RubriqueFixe).filter_by(salarie_id=s.id).order_by(models.RubriqueFixe.est_actif.desc(), models.RubriqueFixe.date_debut.desc()).all()
    return [_fixe_sortie(f) for f in lignes]


@router.post("/{salarie_id}/rubriques-fixes", status_code=201)
def ajouter_fixe(salarie_id: int, corps: RubriqueFixeIn, request: Request, db: Session = Depends(get_db),
                 acteur: models.Utilisateur = Depends(SENSIBLE)):
    if not a_la_permission(acteur, "modifier_salaries"):
        raise HTTPException(status_code=403, detail="Permission manquante : modifier_salaries")
    s = _salarie(db, salarie_id)
    try:
        f = svc_fixes.creer(db, s, corps.code, corps.montant, corps.date_debut, corps.date_fin, corps.commentaire, acteur)
    except svc_fixes.ErreurRubriqueFixe as e:
        raise HTTPException(status_code=422, detail=str(e))
    audit.enregistrer(db, "rubrique_fixe_creee", acteur=acteur, cible_type="salarie", cible_id=s.id,
                      detail={"matricule": s.matricule, "code": f.code, "montant": str(f.montant)}, request=request)
    db.commit()
    db.refresh(f)
    return _fixe_sortie(f)


@router.delete("/{salarie_id}/rubriques-fixes/{fixe_id}")
def arreter_fixe(salarie_id: int, fixe_id: int, request: Request, db: Session = Depends(get_db),
                 acteur: models.Utilisateur = Depends(SENSIBLE)):
    """Désactive la rubrique (jamais supprimée : les anciens bulletins y font référence)."""
    if not a_la_permission(acteur, "modifier_salaries"):
        raise HTTPException(status_code=403, detail="Permission manquante : modifier_salaries")
    s = _salarie(db, salarie_id)
    f = db.get(models.RubriqueFixe, fixe_id)
    if f is None or f.salarie_id != s.id:
        raise HTTPException(status_code=404, detail="Rubrique fixe introuvable.")
    f.est_actif = False
    audit.enregistrer(db, "rubrique_fixe_arretee", acteur=acteur, cible_type="salarie", cible_id=s.id,
                      detail={"matricule": s.matricule, "code": f.code}, request=request)
    db.commit()
    return _fixe_sortie(f)


# ----------------------------------------------------------------- vue d'ensemble du dossier
@router.get("/{salarie_id}/dossier")
def dossier(salarie_id: int, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(VOIR)):
    """Synthèse en lecture seule ; chaque rubrique n'est renvoyée que si le compte a le droit de la voir (sinon null)."""
    s = _salarie(db, salarie_id)
    out: dict = {"bulletins": None, "conges": None, "prets": None, "sanctions": None}
    if a_la_permission(acteur, "voir_donnees_sensibles"):
        lignes = db.query(models.Bulletin, models.Campagne).join(models.Campagne, models.Campagne.id == models.Bulletin.campagne_id)\
            .filter(models.Bulletin.salarie_id == s.id, models.Bulletin.statut == "valide")\
            .order_by(models.Campagne.annee.desc(), models.Campagne.mois.desc(), models.Campagne.numero.desc()).limit(60).all()
        out["bulletins"] = [{"id": b.id, "campagne_id": c.id, "libelle": c.libelle, "annee": c.annee, "mois": c.mois,
                             "total_imposable": b.total_imposable, "net_a_payer": b.net_a_payer} for b, c in lignes]
    if a_la_permission(acteur, "gerer_conges"):
        cs = db.query(models.Conge).filter_by(salarie_id=s.id).order_by(models.Conge.debut.desc()).limit(60).all()
        sol = svc_conges.solde(db, s)
        out["conges"] = {"solde": sol, "elements": [{"id": c.id, "type_conge": c.type_conge, "debut": c.debut, "fin": c.fin,
                                                      "jours_ouvrables": c.jours_ouvrables, "statut": c.statut} for c in cs]}
        out["prets"] = [{"id": p.id, "libelle": p.libelle, "type_pret": p.type_pret, "montant": p.montant, "statut": p.statut,
                         "reste": svc_prets.reste_a_rembourser(p), "regle": svc_prets.montant_regle(p)}
                        for p in db.query(models.Pret).filter_by(salarie_id=s.id).order_by(models.Pret.id.desc()).all()]
    if a_la_permission(acteur, "gerer_discipline"):
        out["sanctions"] = [{"id": m.id, "reference": m.reference, "type_mesure": m.type_mesure, "date_decision": m.date_decision,
                             "motif": m.motif, "statut": m.statut}
                            for m in db.query(models.MesureDisciplinaire).filter_by(salarie_id=s.id)
                            .order_by(models.MesureDisciplinaire.date_decision.desc()).all()]
    return out
