"""Campagnes de paie : préparation, présences, saisies, calcul, validation, bulletins."""
import calendar
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core import models
from ..core.database import get_db
from ..exports import bulletin_pdf
from ..services import audit
from ..services import bulletins as svc
from ..services import salaries as svc_salaries
from .auth_routes import require_any_permission, require_permission

router = APIRouter(tags=["Campagnes de paie"])

LIRE = require_any_permission("lancer_paie", "valider_bulletins", "voir_rapports")


# ----------------------------------------------------------------- schémas
class CampagneIn(BaseModel):
    type_campagne: str = Field(pattern="^(mensuelle|journaliere|exceptionnelle)$")
    annee: int = Field(ge=2000, le=2100)
    mois: int = Field(ge=1, le=12)
    debut: Optional[date] = None
    fin: Optional[date] = None
    libelle: Optional[str] = Field(default=None, max_length=100)
    date_paie: Optional[date] = None


class PresenceIn(BaseModel):
    jours_payes: Optional[Decimal] = Field(default=None, ge=0, le=31)
    jours_presence: Optional[Decimal] = Field(default=None, ge=0, le=31)
    heures_travaillees: Optional[Decimal] = Field(default=None, ge=0, le=400)
    hs1: Optional[Decimal] = Field(default=None, ge=0, le=200)
    hs2: Optional[Decimal] = Field(default=None, ge=0, le=200)
    hs3: Optional[Decimal] = Field(default=None, ge=0, le=200)
    hs4: Optional[Decimal] = Field(default=None, ge=0, le=200)
    heures_absence: Optional[Decimal] = Field(default=None, ge=0, le=400)
    jours_absence_ja: Optional[Decimal] = Field(default=None, ge=0, le=31)


class SaisieIn(BaseModel):
    salarie_id: int
    code: str = Field(max_length=6)
    montant: Decimal = Field(ge=0, le=Decimal("999999999"))
    quantite: Optional[Decimal] = Field(default=None, ge=0)
    libelle: Optional[str] = Field(default=None, max_length=100)
    commentaire: Optional[str] = Field(default=None, max_length=200)


class SaisieMasseIn(BaseModel):
    code: str = Field(max_length=6)
    mode: str = Field(pattern="^(fixe|pourcentage_salaire)$")
    valeur: Decimal = Field(gt=0, le=Decimal("999999999"))
    service_id: Optional[int] = None
    commentaire: Optional[str] = Field(default=None, max_length=200)


class MotifIn(BaseModel):
    motif: str = Field(min_length=5, max_length=300)


class SalarieIdIn(BaseModel):
    salarie_id: int


class PointagesIn(BaseModel):
    ecraser_manuel: bool = False


# ----------------------------------------------------------------- utilitaires
def _camp(db: Session, campagne_id: int) -> models.Campagne:
    c = db.get(models.Campagne, campagne_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Campagne introuvable.")
    return c


def _modifiable(c: models.Campagne) -> None:
    if c.statut in ("validee", "cloturee"):
        raise HTTPException(status_code=409, detail="Campagne validée : modification impossible.")


def _erreur(e: svc.ErreurPaie):
    return HTTPException(status_code=e.statut, detail=str(e))


def _camp_sortie(db: Session, c: models.Campagne) -> dict:
    nb = db.query(func.count()).select_from(models.PresencePeriode).filter_by(campagne_id=c.id).scalar()
    agg = db.query(func.count(models.Bulletin.id), func.coalesce(func.sum(models.Bulletin.net_a_payer), 0),
                   func.coalesce(func.sum(models.Bulletin.total_imposable), 0)).filter_by(campagne_id=c.id).one()
    return {"id": c.id, "libelle": c.libelle, "type_campagne": c.type_campagne, "nature_bulletin": c.nature_bulletin,
            "annee": c.annee, "mois": c.mois, "numero": c.numero, "debut": c.debut, "fin": c.fin, "date_paie": c.date_paie,
            "statut": c.statut, "valide_par": c.valide_par, "valide_le": c.valide_le, "nb_salaries": nb,
            "nb_bulletins": agg[0], "total_net": agg[1], "total_imposable": agg[2]}


def _presence_sortie(p: models.PresencePeriode) -> dict:
    s = p.salarie
    return {"salarie_id": s.id, "matricule": s.matricule, "nom": f"{s.nom} {s.prenoms or ''}".strip(),
            "jours_payes": p.jours_payes, "jours_presence": p.jours_presence, "heures_travaillees": p.heures_travaillees,
            "hs1": p.hs1, "hs2": p.hs2, "hs3": p.hs3, "hs4": p.hs4, "heures_absence": p.heures_absence,
            "jours_absence_ja": p.jours_absence_ja, "source": p.source}


def _bulletin_resume(b: models.Bulletin) -> dict:
    i = b.identite
    return {"id": b.id, "campagne_id": b.campagne_id, "salarie_id": b.salarie_id, "matricule": i["matricule"],
            "nom": f"{i['nom']} {i.get('prenoms') or ''}".strip(), "statut": b.statut, "total_imposable": b.total_imposable,
            "cnps": b.cnps, "its": b.its, "net_a_payer": b.net_a_payer, "anomalies": b.anomalies,
            "envoye_le": b.envoye_le, "lu_le": b.lu_le}


def _bulletin_detail(b: models.Bulletin) -> dict:
    d = _bulletin_resume(b)
    d.update({"identite": b.identite, "lignes": b.lignes, "total_imposable_brut": b.total_imposable_brut,
              "total_retenues_imposables": b.total_retenues_imposables, "total_impots": b.total_impots,
              "gains_non_imposables": b.gains_non_imposables, "retenues_non_imposables": b.retenues_non_imposables,
              "net_non_imposable": b.net_non_imposable, "charges_patronales": b.charges_patronales,
              "valide_par": b.valide_par, "valide_le": b.valide_le, "calcule_le": b.calcule_le})
    return d


# ----------------------------------------------------------------- campagnes
@router.get("/campagnes")
def lister_campagnes(annee: Optional[int] = None, db: Session = Depends(get_db), _=Depends(LIRE)):
    q = db.query(models.Campagne)
    if annee:
        q = q.filter(models.Campagne.annee == annee)
    campagnes = q.order_by(models.Campagne.annee.desc(), models.Campagne.mois.desc(), models.Campagne.numero.desc()).limit(200).all()
    return [_camp_sortie(db, c) for c in campagnes]


@router.post("/campagnes", status_code=201)
def creer_campagne(corps: CampagneIn, request: Request, db: Session = Depends(get_db),
                   acteur: models.Utilisateur = Depends(require_permission("lancer_paie"))):
    if corps.type_campagne == "mensuelle":
        debut, fin = date(corps.annee, corps.mois, 1), date(corps.annee, corps.mois, calendar.monthrange(corps.annee, corps.mois)[1])
        nature = "mensuel"
        numero = 1
    else:
        if not corps.debut or not corps.fin:
            raise HTTPException(status_code=422, detail="Dates de début et de fin obligatoires.")
        debut, fin = corps.debut, corps.fin
        if fin < debut or (fin - debut).days > 31:
            raise HTTPException(status_code=422, detail="Période invalide (31 jours maximum).")
        nature = "journalier" if corps.type_campagne == "journaliere" else "mensuel"
        dernier = db.query(func.max(models.Campagne.numero)).filter_by(annee=corps.annee, mois=corps.mois).scalar() or 0
        numero = dernier + 1
    if db.query(models.Campagne).filter_by(annee=corps.annee, mois=corps.mois, numero=numero).first():
        raise HTTPException(status_code=409, detail="Une campagne mensuelle existe déjà pour cette période.")
    libelle = corps.libelle or (f"Paie {corps.mois:02d}/{corps.annee}" if numero == 1 and nature == "mensuel"
                                else f"Paie {corps.mois:02d}/{corps.annee} n°{numero} ({debut.strftime('%d/%m')} au {fin.strftime('%d/%m')})")
    c = models.Campagne(libelle=libelle, type_campagne=corps.type_campagne, nature_bulletin=nature, annee=corps.annee,
                        mois=corps.mois, numero=numero, debut=debut, fin=fin, date_paie=corps.date_paie, cree_par=acteur.identifiant)
    db.add(c)
    db.flush()
    audit.enregistrer(db, "campagne_creee", acteur=acteur, cible_type="campagne", cible_id=c.id, detail={"libelle": libelle}, request=request)
    db.commit()
    return _camp_sortie(db, c)


@router.get("/campagnes/{campagne_id}")
def detail_campagne(campagne_id: int, db: Session = Depends(get_db), _=Depends(LIRE)):
    c = _camp(db, campagne_id)
    d = _camp_sortie(db, c)
    d["validation"] = {"raisons": svc.verifier_validation(db, c)} if c.statut == "calculee" else {"raisons": []}
    return d


@router.delete("/campagnes/{campagne_id}", status_code=204)
def supprimer_campagne(campagne_id: int, request: Request, db: Session = Depends(get_db),
                       acteur: models.Utilisateur = Depends(require_permission("lancer_paie"))):
    c = _camp(db, campagne_id)
    if c.statut != "ouverte" or db.query(models.Bulletin).filter_by(campagne_id=c.id).count():
        raise HTTPException(status_code=409, detail="Seule une campagne ouverte, sans bulletin calculé, peut être supprimée.")
    audit.enregistrer(db, "campagne_supprimee", acteur=acteur, cible_type="campagne", cible_id=c.id, detail={"libelle": c.libelle}, request=request)
    db.delete(c)
    db.commit()


@router.post("/campagnes/{campagne_id}/initialiser")
def initialiser(campagne_id: int, request: Request, db: Session = Depends(get_db),
                acteur: models.Utilisateur = Depends(require_permission("lancer_paie"))):
    c = _camp(db, campagne_id)
    _modifiable(c)
    n = svc.initialiser(db, c, acteur)
    audit.enregistrer(db, "campagne_initialisee", acteur=acteur, cible_type="campagne", cible_id=c.id, detail={"ajoutes": n}, request=request)
    db.commit()
    return {"ajoutes": n}


# ----------------------------------------------------------------- présences
@router.get("/campagnes/{campagne_id}/presences")
def lister_presences(campagne_id: int, db: Session = Depends(get_db), _=Depends(LIRE)):
    _camp(db, campagne_id)
    lignes = db.query(models.PresencePeriode).join(models.Salarie).filter(models.PresencePeriode.campagne_id == campagne_id)\
        .order_by(models.Salarie.matricule).all()
    return [_presence_sortie(p) for p in lignes]


@router.post("/campagnes/{campagne_id}/salaries")
def ajouter_salarie(campagne_id: int, corps: SalarieIdIn, request: Request, db: Session = Depends(get_db),
                    acteur: models.Utilisateur = Depends(require_permission("lancer_paie"))):
    c = _camp(db, campagne_id)
    _modifiable(c)
    s = db.get(models.Salarie, corps.salarie_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Salarié introuvable.")
    if db.get(models.PresencePeriode, (c.id, s.id)):
        raise HTTPException(status_code=409, detail="Salarié déjà dans la campagne.")
    db.add(models.PresencePeriode(campagne_id=c.id, salarie_id=s.id, jours_payes=svc.jours_payes_par_defaut(s, c), modifie_par=acteur.identifiant))
    audit.enregistrer(db, "campagne_salarie_ajoute", acteur=acteur, cible_type="campagne", cible_id=c.id, detail={"matricule": s.matricule}, request=request)
    db.commit()
    return {"ok": True}


@router.delete("/campagnes/{campagne_id}/salaries/{salarie_id}", status_code=204)
def retirer_salarie(campagne_id: int, salarie_id: int, request: Request, db: Session = Depends(get_db),
                    acteur: models.Utilisateur = Depends(require_permission("lancer_paie"))):
    c = _camp(db, campagne_id)
    _modifiable(c)
    p = db.get(models.PresencePeriode, (c.id, salarie_id))
    if p is None:
        raise HTTPException(status_code=404, detail="Salarié absent de la campagne.")
    db.query(models.SaisieRubrique).filter_by(campagne_id=c.id, salarie_id=salarie_id).delete()
    db.query(models.Bulletin).filter_by(campagne_id=c.id, salarie_id=salarie_id, statut="brouillon").delete()
    audit.enregistrer(db, "campagne_salarie_retire", acteur=acteur, cible_type="campagne", cible_id=c.id, detail={"matricule": p.salarie.matricule}, request=request)
    db.delete(p)
    db.commit()


@router.post("/campagnes/{campagne_id}/presences/depuis-pointages")
def presences_depuis_pointages(campagne_id: int, corps: PointagesIn, request: Request, db: Session = Depends(get_db),
                               acteur: models.Utilisateur = Depends(require_permission("lancer_paie"))):
    c = _camp(db, campagne_id)
    _modifiable(c)
    resume = svc.presences_depuis_pointages(db, c, acteur, corps.ecraser_manuel)
    audit.enregistrer(db, "presences_depuis_pointages", acteur=acteur, cible_type="campagne", cible_id=c.id,
                      detail={k: v for k, v in resume.items() if k != "absences_proposees"}, request=request)
    db.commit()
    return resume


@router.put("/campagnes/{campagne_id}/presences/{salarie_id}")
def modifier_presence(campagne_id: int, salarie_id: int, corps: PresenceIn, request: Request, db: Session = Depends(get_db),
                      acteur: models.Utilisateur = Depends(require_permission("lancer_paie"))):
    c = _camp(db, campagne_id)
    _modifiable(c)
    p = db.get(models.PresencePeriode, (c.id, salarie_id))
    if p is None:
        raise HTTPException(status_code=404, detail="Salarié absent de la campagne.")
    changements = corps.model_dump(exclude_unset=True, exclude_none=True)
    for k, v in changements.items():
        setattr(p, k, v)
    p.source, p.modifie_par, p.modifie_le = "manuel", acteur.identifiant, datetime.now(timezone.utc)
    audit.enregistrer(db, "presence_modifiee", acteur=acteur, cible_type="campagne", cible_id=c.id,
                      detail={"matricule": p.salarie.matricule, **{k: str(v) for k, v in changements.items()}}, request=request)
    db.commit()
    db.refresh(p)
    return _presence_sortie(p)


# ----------------------------------------------------------------- saisies de rubriques
def _saisie_sortie(s: models.SaisieRubrique, matricule: str) -> dict:
    return {"id": s.id, "salarie_id": s.salarie_id, "matricule": matricule, "code": s.code, "libelle": s.libelle, "type": s.type,
            "montant": s.montant, "quantite": s.quantite, "commentaire": s.commentaire, "origine": s.origine}


@router.get("/campagnes/{campagne_id}/saisies")
def lister_saisies(campagne_id: int, db: Session = Depends(get_db), _=Depends(LIRE)):
    _camp(db, campagne_id)
    lignes = db.query(models.SaisieRubrique, models.Salarie.matricule).join(models.Salarie).filter(
        models.SaisieRubrique.campagne_id == campagne_id).order_by(models.Salarie.matricule, models.SaisieRubrique.id).all()
    return [_saisie_sortie(s, m) for s, m in lignes]


@router.post("/campagnes/{campagne_id}/saisies", status_code=201)
def ajouter_saisie(campagne_id: int, corps: SaisieIn, request: Request, db: Session = Depends(get_db),
                   acteur: models.Utilisateur = Depends(require_permission("lancer_paie"))):
    c = _camp(db, campagne_id)
    _modifiable(c)
    p = db.get(models.PresencePeriode, (c.id, corps.salarie_id))
    if p is None:
        raise HTTPException(status_code=404, detail="Salarié absent de la campagne.")
    r = db.get(models.Rubrique, corps.code.upper())
    if r is None or not r.est_actif:
        raise HTTPException(status_code=422, detail="Rubrique inconnue ou inactive.")
    s = models.SaisieRubrique(campagne_id=c.id, salarie_id=corps.salarie_id, code=r.code, libelle=corps.libelle or r.libelle,
                              type=r.type, montant=corps.montant, quantite=corps.quantite, commentaire=corps.commentaire,
                              origine="manuelle", cree_par=acteur.identifiant)
    db.add(s)
    db.flush()
    audit.enregistrer(db, "saisie_ajoutee", acteur=acteur, cible_type="campagne", cible_id=c.id,
                      detail={"matricule": p.salarie.matricule, "code": r.code, "montant": str(corps.montant)}, request=request)
    db.commit()
    return _saisie_sortie(s, p.salarie.matricule)


@router.post("/campagnes/{campagne_id}/saisies/en-masse")
def saisie_en_masse(campagne_id: int, corps: SaisieMasseIn, request: Request, db: Session = Depends(get_db),
                    acteur: models.Utilisateur = Depends(require_permission("lancer_paie"))):
    """Même rubrique pour tous les salariés de la campagne (ou d'un service) : gratification, prime de fin d'année...
    Mode « pourcentage_salaire » : % du salaire catégoriel + sursalaire en vigueur à la fin de la période."""
    c = _camp(db, campagne_id)
    _modifiable(c)
    r = db.get(models.Rubrique, corps.code.upper())
    if r is None or not r.est_actif:
        raise HTTPException(status_code=422, detail="Rubrique inconnue ou inactive.")
    n, ignores = 0, []
    for p in db.query(models.PresencePeriode).filter_by(campagne_id=c.id).all():
        s = p.salarie
        if corps.service_id and s.service_id != corps.service_id:
            continue
        if corps.mode == "fixe":
            montant = corps.valeur
        else:
            e = svc_salaries.salaire_en_vigueur(s, c.fin)
            if e is None:
                ignores.append(s.matricule)
                continue
            montant = ((e.montant + (e.sursalaire or 0)) * corps.valeur / 100).quantize(Decimal("0.01"))
        db.add(models.SaisieRubrique(campagne_id=c.id, salarie_id=s.id, code=r.code, libelle=r.libelle, type=r.type,
                                     montant=montant, commentaire=corps.commentaire, origine="manuelle", cree_par=acteur.identifiant))
        n += 1
    audit.enregistrer(db, "saisie_en_masse", acteur=acteur, cible_type="campagne", cible_id=c.id,
                      detail={"code": r.code, "mode": corps.mode, "valeur": str(corps.valeur), "salaries": n}, request=request)
    db.commit()
    return {"ajoutees": n, "ignores_sans_salaire": ignores}


@router.delete("/campagnes/{campagne_id}/saisies/{saisie_id}", status_code=204)
def supprimer_saisie(campagne_id: int, saisie_id: int, request: Request, db: Session = Depends(get_db),
                     acteur: models.Utilisateur = Depends(require_permission("lancer_paie"))):
    c = _camp(db, campagne_id)
    _modifiable(c)
    s = db.get(models.SaisieRubrique, saisie_id)
    if s is None or s.campagne_id != c.id:
        raise HTTPException(status_code=404, detail="Saisie introuvable.")
    if s.origine != "manuelle":
        raise HTTPException(status_code=409, detail="Cette ligne provient d'un module (prêt, solde...) : modifiez-la à la source.")
    audit.enregistrer(db, "saisie_supprimee", acteur=acteur, cible_type="campagne", cible_id=c.id,
                      detail={"salarie_id": s.salarie_id, "code": s.code, "montant": str(s.montant)}, request=request)
    db.delete(s)
    db.commit()


# ----------------------------------------------------------------- calcul et validation
@router.post("/campagnes/{campagne_id}/calculer")
def calculer(campagne_id: int, request: Request, salarie_id: Optional[int] = None, db: Session = Depends(get_db),
             acteur: models.Utilisateur = Depends(require_permission("lancer_paie"))):
    c = _camp(db, campagne_id)
    try:
        if salarie_id:
            p = db.get(models.PresencePeriode, (c.id, salarie_id))
            if p is None:
                raise HTTPException(status_code=404, detail="Salarié absent de la campagne.")
            b = svc.calculer_un(db, c, p)
            if c.statut == "ouverte":
                c.statut = "calculee"
            resume = {"calcules": 1, "erreurs": [], "anomalies": 1 if b.anomalies else 0}
        else:
            resume = svc.calculer_campagne(db, c)
    except svc.ErreurPaie as e:
        db.rollback()
        raise _erreur(e)
    audit.enregistrer(db, "campagne_calculee", acteur=acteur, cible_type="campagne", cible_id=c.id,
                      detail={"calcules": resume["calcules"], "erreurs": len(resume["erreurs"]), "anomalies": resume["anomalies"]}, request=request)
    db.commit()
    return resume


@router.post("/campagnes/{campagne_id}/valider")
def valider(campagne_id: int, request: Request, db: Session = Depends(get_db),
            acteur: models.Utilisateur = Depends(require_permission("valider_bulletins"))):
    c = _camp(db, campagne_id)
    try:
        n = svc.valider(db, c, acteur)
    except svc.ErreurPaie as e:
        db.rollback()
        raise _erreur(e)
    audit.enregistrer(db, "campagne_validee", acteur=acteur, cible_type="campagne", cible_id=c.id, detail={"bulletins": n}, request=request)
    db.commit()
    return {"bulletins_valides": n}


@router.post("/campagnes/{campagne_id}/rouvrir")
def rouvrir(campagne_id: int, corps: MotifIn, request: Request, db: Session = Depends(get_db),
            acteur: models.Utilisateur = Depends(require_permission("valider_bulletins"))):
    if acteur.role != "admin":
        raise HTTPException(status_code=403, detail="Seul un administrateur peut rouvrir une campagne validée.")
    c = _camp(db, campagne_id)
    try:
        svc.rouvrir(db, c)
    except svc.ErreurPaie as e:
        db.rollback()
        raise _erreur(e)
    audit.enregistrer(db, "campagne_rouverte", acteur=acteur, cible_type="campagne", cible_id=c.id, detail={"motif": corps.motif}, request=request)
    db.commit()
    return {"statut": c.statut}


@router.post("/campagnes/{campagne_id}/cloturer")
def cloturer(campagne_id: int, request: Request, db: Session = Depends(get_db),
             acteur: models.Utilisateur = Depends(require_permission("valider_bulletins"))):
    c = _camp(db, campagne_id)
    if c.statut != "validee":
        raise HTTPException(status_code=409, detail="Seule une campagne validée peut être clôturée.")
    c.statut, c.cloture_le = "cloturee", datetime.now(timezone.utc)
    audit.enregistrer(db, "campagne_cloturee", acteur=acteur, cible_type="campagne", cible_id=c.id, request=request)
    db.commit()
    return {"statut": c.statut}


# ----------------------------------------------------------------- bulletins
@router.get("/campagnes/{campagne_id}/bulletins")
def lister_bulletins(campagne_id: int, db: Session = Depends(get_db), _=Depends(LIRE)):
    _camp(db, campagne_id)
    lignes = db.query(models.Bulletin).join(models.Salarie).filter(models.Bulletin.campagne_id == campagne_id)\
        .order_by(models.Salarie.matricule).all()
    return [_bulletin_resume(b) for b in lignes]


@router.get("/bulletins/{bulletin_id}")
def detail_bulletin(bulletin_id: int, request: Request, db: Session = Depends(get_db),
                    acteur: models.Utilisateur = Depends(LIRE)):
    b = db.get(models.Bulletin, bulletin_id)
    if b is None:
        raise HTTPException(status_code=404, detail="Bulletin introuvable.")
    return _bulletin_detail(b)


def _pdf(db: Session, campagne: models.Campagne, bulletins: list, nom: str) -> Response:
    return Response(content=bulletin_pdf.generer(db, campagne, bulletins), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{nom}.pdf"'})


@router.get("/bulletins/{bulletin_id}/pdf")
def pdf_bulletin(bulletin_id: int, request: Request, db: Session = Depends(get_db),
                 acteur: models.Utilisateur = Depends(LIRE)):
    b = db.get(models.Bulletin, bulletin_id)
    if b is None:
        raise HTTPException(status_code=404, detail="Bulletin introuvable.")
    c = db.get(models.Campagne, b.campagne_id)
    audit.enregistrer(db, "bulletin_imprime", acteur=acteur, cible_type="bulletin", cible_id=b.id, request=request)
    db.commit()
    return _pdf(db, c, [b], f"bulletin_{b.identite['matricule']}_{c.annee}{c.mois:02d}_{c.numero}")


@router.get("/campagnes/{campagne_id}/bulletins.pdf")
def pdf_campagne(campagne_id: int, request: Request, db: Session = Depends(get_db),
                 acteur: models.Utilisateur = Depends(LIRE)):
    c = _camp(db, campagne_id)
    bulletins = db.query(models.Bulletin).join(models.Salarie).filter(models.Bulletin.campagne_id == c.id)\
        .order_by(models.Salarie.matricule).all()
    audit.enregistrer(db, "bulletins_imprimes", acteur=acteur, cible_type="campagne", cible_id=c.id, detail={"nombre": len(bulletins)}, request=request)
    db.commit()
    return _pdf(db, c, bulletins, f"bulletins_{c.annee}{c.mois:02d}_{c.numero}")
