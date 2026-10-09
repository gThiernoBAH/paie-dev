"""Dossier disciplinaire (avertissements, blâmes, mises à pied) et notes de service."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from ..core import models
from ..core.database import get_db
from ..exports import lettres_pdf
from ..services import audit
from ..services import discipline as svc
from .auth_routes import require_permission

router = APIRouter(tags=["Discipline"])
GERER = require_permission("gerer_discipline")


class MesureIn(BaseModel):
    salarie_id: int
    type_mesure: str = Field(pattern="^(avertissement|blame|mise_a_pied)$")
    date_faits: Optional[date] = None
    date_decision: date
    motif: str = Field(min_length=5, max_length=3000)
    debut_mise_a_pied: Optional[date] = None
    fin_mise_a_pied: Optional[date] = None

    @model_validator(mode="after")
    def _coherence(self):
        if self.type_mesure == "mise_a_pied":
            if not self.debut_mise_a_pied or not self.fin_mise_a_pied:
                raise ValueError("Une mise à pied exige une date de début et une date de fin.")
            if self.fin_mise_a_pied < self.debut_mise_a_pied:
                raise ValueError("La fin de la mise à pied précède son début.")
        else:
            self.debut_mise_a_pied = self.fin_mise_a_pied = None
        if self.date_faits and self.date_faits > self.date_decision:
            raise ValueError("La date des faits est postérieure à la décision.")
        return self


class AnnulationIn(BaseModel):
    motif: str = Field(min_length=3, max_length=200)


class NoteIn(BaseModel):
    objet: str = Field(min_length=3, max_length=150)
    contenu: str = Field(min_length=5, max_length=8000)
    date_effet: date
    service_id: Optional[int] = None


def _mesure_sortie(db: Session, m: models.MesureDisciplinaire) -> dict:
    s = m.salarie
    jours = None
    if m.type_mesure == "mise_a_pied":
        jours = int(svc.jours_mise_a_pied(db, s.id, m.debut_mise_a_pied, m.fin_mise_a_pied)) if m.statut == "active" else 0
    return {"id": m.id, "reference": m.reference, "salarie_id": s.id, "matricule": s.matricule, "nom": f"{s.nom} {s.prenoms or ''}".strip(),
            "type_mesure": m.type_mesure, "type_libelle": svc.LIBELLES[m.type_mesure], "date_faits": m.date_faits,
            "date_decision": m.date_decision, "motif": m.motif, "debut_mise_a_pied": m.debut_mise_a_pied, "fin_mise_a_pied": m.fin_mise_a_pied,
            "jours_non_payes": jours, "statut": m.statut, "cree_par": m.cree_par, "annule_par": m.annule_par, "motif_annulation": m.motif_annulation}


def _get_mesure(db: Session, mid: int) -> models.MesureDisciplinaire:
    m = db.get(models.MesureDisciplinaire, mid)
    if m is None:
        raise HTTPException(status_code=404, detail="Mesure introuvable.")
    return m


@router.get("/discipline/mesures")
def lister_mesures(salarie_id: Optional[int] = None, db: Session = Depends(get_db), _=Depends(GERER)):
    q = db.query(models.MesureDisciplinaire)
    if salarie_id:
        q = q.filter_by(salarie_id=salarie_id)
    return [_mesure_sortie(db, m) for m in q.order_by(models.MesureDisciplinaire.date_decision.desc(), models.MesureDisciplinaire.id.desc()).limit(2000).all()]


@router.post("/discipline/mesures", status_code=201)
def creer_mesure(corps: MesureIn, request: Request, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(GERER)):
    s = db.get(models.Salarie, corps.salarie_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Salarié introuvable.")
    if not s.est_actif:
        raise HTTPException(status_code=409, detail="Ce salarié n'est plus en activité.")
    m = svc.creer_mesure(db, **corps.model_dump(), cree_par=acteur.identifiant)
    audit.enregistrer(db, "mesure_disciplinaire_creee", acteur=acteur, cible_type="mesure_disciplinaire", cible_id=m.id,
                      detail={"matricule": s.matricule, "type": m.type_mesure, "reference": m.reference}, request=request)
    db.commit()
    return _mesure_sortie(db, m)


@router.post("/discipline/mesures/{mid}/annuler")
def annuler_mesure(mid: int, corps: AnnulationIn, request: Request, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(GERER)):
    m = _get_mesure(db, mid)
    if m.statut == "annulee":
        raise HTTPException(status_code=409, detail="Cette mesure est déjà annulée.")
    from datetime import datetime, timezone
    m.statut, m.annule_par, m.annule_le, m.motif_annulation = "annulee", acteur.identifiant, datetime.now(timezone.utc), corps.motif
    audit.enregistrer(db, "mesure_disciplinaire_annulee", acteur=acteur, cible_type="mesure_disciplinaire", cible_id=m.id,
                      detail={"reference": m.reference, "motif": corps.motif}, request=request)
    db.commit()
    return _mesure_sortie(db, m)


@router.get("/discipline/mesures/{mid}/lettre.pdf")
def lettre(mid: int, request: Request, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(GERER)):
    m = _get_mesure(db, mid)
    audit.enregistrer(db, "mesure_disciplinaire_lettre", acteur=acteur, cible_type="mesure_disciplinaire", cible_id=m.id, request=request)
    db.commit()
    return Response(content=lettres_pdf.lettre_mesure(db, m), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{m.reference}.pdf"'})


# ----------------------------------------------------------------- notes de service
def _note_sortie(n: models.NoteService) -> dict:
    return {"id": n.id, "reference": n.reference, "objet": n.objet, "contenu": n.contenu, "date_effet": n.date_effet,
            "service_id": n.service_id, "service": n.service.libelle if n.service else "Tout le personnel",
            "statut": n.statut, "cree_par": n.cree_par}


@router.get("/discipline/notes")
def lister_notes(db: Session = Depends(get_db), _=Depends(GERER)):
    return [_note_sortie(n) for n in db.query(models.NoteService).order_by(models.NoteService.date_effet.desc(), models.NoteService.id.desc()).limit(2000).all()]


@router.post("/discipline/notes", status_code=201)
def creer_note(corps: NoteIn, request: Request, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(GERER)):
    if corps.service_id:
        ref = db.get(models.Referentiel, corps.service_id)
        if ref is None or ref.type_ref != "service":
            raise HTTPException(status_code=422, detail="Service inconnu.")
    n = svc.creer_note(db, **corps.model_dump(), cree_par=acteur.identifiant)
    audit.enregistrer(db, "note_service_creee", acteur=acteur, cible_type="note_service", cible_id=n.id,
                      detail={"reference": n.reference, "objet": n.objet}, request=request)
    db.commit()
    return _note_sortie(n)


@router.post("/discipline/notes/{nid}/annuler")
def annuler_note(nid: int, request: Request, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(GERER)):
    n = db.get(models.NoteService, nid)
    if n is None:
        raise HTTPException(status_code=404, detail="Note introuvable.")
    n.statut = "annulee"
    audit.enregistrer(db, "note_service_annulee", acteur=acteur, cible_type="note_service", cible_id=n.id, request=request)
    db.commit()
    return _note_sortie(n)


@router.get("/discipline/notes/{nid}/pdf")
def pdf_note(nid: int, db: Session = Depends(get_db), _=Depends(GERER)):
    n = db.get(models.NoteService, nid)
    if n is None:
        raise HTTPException(status_code=404, detail="Note introuvable.")
    return Response(content=lettres_pdf.note_de_service(db, n), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{n.reference}.pdf"'})
