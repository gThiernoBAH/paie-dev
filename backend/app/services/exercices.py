"""Clôture annuelle : une année clôturée est verrouillée (plus de campagne, de salaire ni de règlement de prêt daté dedans)
et ses cumuls par salarié sont figés. Seul un administrateur peut la rouvrir, avec un motif."""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional, Union

from sqlalchemy.orm import Session

from ..core import models
from . import rapports


class ErreurExercice(ValueError):
    pass


def est_cloture(db: Session, annee: int) -> bool:
    e = db.get(models.Exercice, annee)
    return e is not None and e.statut == "cloture"


def message_si_cloture(db: Session, quand: Union[int, date, None]) -> Optional[str]:
    """Texte d'erreur si l'année (ou la date) tombe dans un exercice clôturé, sinon None."""
    if quand is None:
        return None
    annee = quand if isinstance(quand, int) else quand.year
    if est_cloture(db, annee):
        return f"L'exercice {annee} est clôturé : cette opération est interdite. Un administrateur peut le rouvrir."
    return None


def prerequis(db: Session, annee: int) -> list:
    """Raisons qui empêchent la clôture (liste vide = clôture possible)."""
    camps = db.query(models.Campagne).filter(models.Campagne.annee == annee).all()
    raisons = []
    if not any(c.statut in ("validee", "cloturee") for c in camps):
        raisons.append(f"Aucune paie validée en {annee}.")
    for c in camps:
        if c.statut not in ("validee", "cloturee"):
            raisons.append(f"La campagne « {c.libelle} » n'est pas validée ({c.statut}).")
    return raisons


def _json(v):
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (list, tuple)):
        return [_json(x) for x in v]
    if isinstance(v, dict):
        return {k: _json(x) for k, x in v.items()}
    return v


def cloturer(db: Session, annee: int, acteur: models.Utilisateur) -> models.Exercice:
    if est_cloture(db, annee):
        raise ErreurExercice(f"L'exercice {annee} est déjà clôturé.")
    if annee >= date.today().year + 1:
        raise ErreurExercice("Impossible de clôturer une année future.")
    raisons = prerequis(db, annee)
    if raisons:
        raise ErreurExercice(" ".join(raisons))
    maintenant = datetime.now(timezone.utc)
    for c in db.query(models.Campagne).filter(models.Campagne.annee == annee, models.Campagne.statut == "validee").all():
        c.statut, c.cloture_le = "cloturee", maintenant
    instantane = _json(rapports.cumuls_annuels(db, annee))
    e = db.get(models.Exercice, annee) or models.Exercice(annee=annee)
    e.statut, e.cloture_le, e.cloture_par, e.instantane = "cloture", maintenant, acteur.identifiant, instantane
    e.rouvert_le = e.rouvert_par = e.motif_reouverture = None
    db.add(e)
    db.flush()
    return e


def rouvrir(db: Session, annee: int, acteur: models.Utilisateur, motif: str) -> models.Exercice:
    e = db.get(models.Exercice, annee)
    if e is None or e.statut != "cloture":
        raise ErreurExercice(f"L'exercice {annee} n'est pas clôturé.")
    e.statut, e.rouvert_le, e.rouvert_par, e.motif_reouverture = "rouvert", datetime.now(timezone.utc), acteur.identifiant, motif
    db.flush()
    return e


def liste(db: Session) -> list:
    annees = {a for (a,) in db.query(models.Campagne.annee).distinct().all()}
    annees |= {e.annee for e in db.query(models.Exercice).all()}
    annees.add(date.today().year)
    sortie = []
    for a in sorted(annees, reverse=True):
        e = db.get(models.Exercice, a)
        camps = db.query(models.Campagne).filter(models.Campagne.annee == a).all()
        sortie.append({
            "annee": a, "statut": e.statut if e else "ouvert", "cloture_le": e.cloture_le if e else None,
            "cloture_par": e.cloture_par if e else None, "rouvert_par": e.rouvert_par if e else None,
            "motif_reouverture": e.motif_reouverture if e else None,
            "campagnes": len(camps), "campagnes_validees": sum(1 for c in camps if c.statut in ("validee", "cloturee")),
            "raisons": [] if (e and e.statut == "cloture") else prerequis(db, a),
        })
    return sortie
