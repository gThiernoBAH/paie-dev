"""Congés : jours ouvrables, soldes acquis/pris."""
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from ..core import models
from ..moteur.calcul import mois_complets
from . import parametres as param


def jours_ouvrables(db: Session, debut: date, fin: date) -> Decimal:
    """Jours du lundi au samedi, hors jours fériés (le dimanche est le jour de repos)."""
    feries = {f.jour for f in db.query(models.JourFerie).filter(models.JourFerie.jour >= debut, models.JourFerie.jour <= fin).all()}
    n, j = 0, debut
    while j <= fin:
        if j.weekday() != 6 and j not in feries:
            n += 1
        j += timedelta(days=1)
    return Decimal(n)


def solde(db: Session, s: models.Salarie, a_la_date: Optional[date] = None) -> dict:
    """Solde de congés annuels : initial + acquis depuis la date de référence − congés annuels approuvés."""
    jour = a_la_date or date.today()
    reference = s.solde_conges_date or s.date_embauche
    par_mois = Decimal(str(param.lire(db, "conges_jours_ouvrables_par_mois", jour)))
    acquis = Decimal(0)
    if reference:
        acquis = (Decimal(mois_complets(reference, min(jour, s.date_sortie) if s.date_sortie else jour)) * par_mois).quantize(Decimal("0.1"))
    q = db.query(models.Conge).filter(models.Conge.salarie_id == s.id, models.Conge.type_conge == "annuel",
                                      models.Conge.statut == "approuve")
    if s.solde_conges_date:
        q = q.filter(models.Conge.debut >= s.solde_conges_date)
    pris = sum((c.jours_ouvrables for c in q.all()), Decimal(0))
    initial = Decimal(s.solde_conges_initial or 0)
    return {"initial": initial, "acquis": acquis, "pris": pris, "solde": initial + acquis - pris}
