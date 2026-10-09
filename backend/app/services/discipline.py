"""Dossier disciplinaire : mesures (avertissement, blâme, mise à pied) et notes de service.

La mise à pied est une absence non payée : les jours OUVRÉS (lundi–vendredi, hors jours fériés) couverts
par la mise à pied et situés dans la période d'une campagne mensuelle s'ajoutent aux « Absences (jours) ».
"""
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from ..core import models

LIBELLES = {"avertissement": "Avertissement", "blame": "Blâme", "mise_a_pied": "Mise à pied"}


def _reference(prefixe: str, annee: int, numero: int) -> str:
    return f"{prefixe}-{annee}-{numero:04d}"


def creer_mesure(db: Session, **champs) -> models.MesureDisciplinaire:
    m = models.MesureDisciplinaire(**champs)
    db.add(m)
    db.flush()
    m.reference = _reference("DISC", m.date_decision.year, m.id)
    db.flush()
    return m


def creer_note(db: Session, **champs) -> models.NoteService:
    n = models.NoteService(**champs)
    db.add(n)
    db.flush()
    n.reference = _reference("NS", n.date_effet.year, n.id)
    db.flush()
    return n


def jours_ouvres(db: Session, debut: date, fin: date) -> list[date]:
    feries = {f.jour for f in db.query(models.JourFerie).filter(models.JourFerie.jour.between(debut, fin)).all()}
    jours, j = [], debut
    while j <= fin:
        if j.weekday() < 5 and j not in feries:
            jours.append(j)
        j += timedelta(days=1)
    return jours


def jours_mise_a_pied(db: Session, salarie_id: int, debut: date, fin: date) -> Decimal:
    """Jours ouvrés de mise à pied (mesures actives) recouvrant la période [debut, fin]."""
    total = 0
    mesures = db.query(models.MesureDisciplinaire).filter(
        models.MesureDisciplinaire.salarie_id == salarie_id, models.MesureDisciplinaire.type_mesure == "mise_a_pied",
        models.MesureDisciplinaire.statut == "active", models.MesureDisciplinaire.debut_mise_a_pied <= fin,
        models.MesureDisciplinaire.fin_mise_a_pied >= debut).all()
    vus: set[date] = set()
    for m in mesures:
        a, b = max(m.debut_mise_a_pied, debut), min(m.fin_mise_a_pied, fin)
        vus.update(jours_ouvres(db, a, b))
    total = len(vus)
    return Decimal(total)


def mises_a_pied_du_mois(db: Session, campagne: models.Campagne) -> dict[int, Decimal]:
    """{salarie_id: jours} pour l'information des écrans de campagne (mensuel uniquement)."""
    if campagne.nature_bulletin != "mensuel":
        return {}
    ids = {m.salarie_id for m in db.query(models.MesureDisciplinaire).filter(
        models.MesureDisciplinaire.type_mesure == "mise_a_pied", models.MesureDisciplinaire.statut == "active",
        models.MesureDisciplinaire.debut_mise_a_pied <= campagne.fin, models.MesureDisciplinaire.fin_mise_a_pied >= campagne.debut).all()}
    return {i: jours_mise_a_pied(db, i, campagne.debut, campagne.fin) for i in ids}
