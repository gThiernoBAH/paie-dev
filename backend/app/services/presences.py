"""Calcul des présences à partir des pointages : heures normales, heures supplémentaires, absences.

Règles (toutes pilotées par les paramètres, cf. écran Paramétrage) :
  * durée d'un jour = sortie - entrée (passage de minuit géré), moins la pause si la présence dépasse le seuil ;
  * dimanche ou jour férié : toutes les heures sont des heures supplémentaires, HS3 de jour et HS4 pour la
    part située dans la plage de nuit ;
  * autres jours : les heures s'additionnent dans la semaine (lundi-dimanche) ; jusqu'à 40 h = normales,
    de 40 h à 46 h = HS1, au-delà = HS2. Le cumul tient compte des jours de la semaine antérieurs à la période.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from ..core.models import JourFerie, Pointage, Salarie
from . import parametres as param

MINUTES_JOUR = 24 * 60


@dataclass
class PresenceCalculee:
    jours_presence: int = 0
    heures_normales: Decimal = Decimal(0)
    heures_sup: dict = field(default_factory=lambda: {1: Decimal(0), 2: Decimal(0), 3: Decimal(0), 4: Decimal(0)})
    absences_detectees: list = field(default_factory=list)   # jours ouvrés sans pointage
    jours_sans_sortie: list = field(default_factory=list)    # pointages incomplets (anomalies)
    detail: list = field(default_factory=list)


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _plage_nuit_minutes(debut: int, duree: int, nuit_debut: int, nuit_fin: int) -> int:
    """Minutes de [debut, debut+duree) situées dans la plage de nuit (qui peut enjamber minuit)."""
    total = 0
    for m in range(debut, debut + duree):
        h = m % MINUTES_JOUR
        if (nuit_debut > nuit_fin and (h >= nuit_debut or h < nuit_fin)) or (nuit_debut <= nuit_fin and nuit_debut <= h < nuit_fin):
            total += 1
    return total


def duree_travaillee(entree: time, sortie: time, pause_minutes: int, seuil_heures: Decimal) -> int:
    """Minutes effectivement travaillées sur une journée."""
    debut, fin = _minutes(entree), _minutes(sortie)
    if fin <= debut:
        fin += MINUTES_JOUR   # sortie après minuit
    duree = fin - debut
    if Decimal(duree) / 60 > seuil_heures:
        duree -= pause_minutes
    return max(0, duree)


def _heure_vers_minutes(texte: str) -> int:
    h, m = texte.split(":")[:2]
    return int(h) * 60 + int(m)


def calculer(db: Session, salarie: Salarie, debut: date, fin: date) -> PresenceCalculee:
    pause = int(param.lire(db, "pointage_pause_minutes", fin))
    seuil = param.lire(db, "pointage_pause_seuil_heures", fin)
    nuit_d = _heure_vers_minutes(param.lire(db, "nuit_debut", fin))
    nuit_f = _heure_vers_minutes(param.lire(db, "nuit_fin", fin))
    base_hebdo = param.lire(db, "heures_hebdo", fin)
    limite_hs1 = param.lire(db, "hs_limite_tranche1", fin)
    jours_ouvres = {int(x) for x in re.findall(r"\d", param.lire(db, "pointage_jours_ouvres", fin))}

    # On remonte au lundi de la semaine de début pour connaître le cumul déjà atteint.
    lundi = debut - timedelta(days=debut.weekday())
    pointages = {
        p.jour: p for p in db.query(Pointage).filter(
            Pointage.salarie_id == salarie.id, Pointage.jour >= lundi, Pointage.jour <= fin).all()
    }
    feries = {f.jour for f in db.query(JourFerie).filter(JourFerie.jour >= debut, JourFerie.jour <= fin).all()}

    res = PresenceCalculee()
    cumul_semaine = {}   # lundi -> minutes déjà comptées dans la semaine (jours ordinaires)
    for jour in (lundi + timedelta(days=i) for i in range((fin - lundi).days + 1)):
        p = pointages.get(jour)
        dans_periode = jour >= debut
        est_repos = jour.weekday() == 6 or jour in feries
        if p is None or p.heure_entree is None or p.heure_sortie is None:
            if p is not None and dans_periode:
                res.jours_sans_sortie.append(jour)
            if dans_periode and p is None and not est_repos and (jour.weekday() + 1) in jours_ouvres:
                res.absences_detectees.append(jour)
            continue
        minutes = duree_travaillee(p.heure_entree, p.heure_sortie, pause, seuil)
        if minutes <= 0:
            continue
        semaine = jour - timedelta(days=jour.weekday())
        if est_repos:
            nuit = _plage_nuit_minutes(_minutes(p.heure_entree), minutes, nuit_d, nuit_f)
            repartition = {"HS3": minutes - nuit, "HS4": nuit}
        else:
            deja = cumul_semaine.get(semaine, 0)
            cumul_semaine[semaine] = deja + minutes
            seuil1, seuil2 = int(base_hebdo * 60), int(limite_hs1 * 60)
            normales = max(0, min(minutes, seuil1 - deja))
            hs1 = max(0, min(deja + minutes, seuil2) - max(deja, seuil1))
            hs2 = minutes - normales - hs1
            repartition = {"N": normales, "HS1": hs1, "HS2": hs2}
        if not dans_periode:
            continue
        res.jours_presence += 1
        res.heures_normales += Decimal(repartition.get("N", 0)) / 60
        for cle in ("HS1", "HS2", "HS3", "HS4"):
            res.heures_sup[int(cle[2])] += Decimal(repartition.get(cle, 0)) / 60
        res.detail.append({"jour": jour, "minutes": minutes, **repartition})
    res.heures_normales = res.heures_normales.quantize(Decimal("0.01"))
    res.heures_sup = {k: v.quantize(Decimal("0.01")) for k, v in res.heures_sup.items()}
    return res
