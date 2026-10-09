"""Simulation de bulletin : le moteur de paie sur des hypothèses, sans rien enregistrer."""
import calendar
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from ..core import models
from ..moteur import calcul
from ..moteur.modeles import EntreeBulletin, Rubrique
from ..moteur.parametres_paie import charger
from . import rubriques_fixes as svc_fixes
from . import salaries as svc_salaries
from .bulletins import ErreurPaie, lignes_vers_json, vers_json

D = Decimal


def simuler(db: Session, annee: int, mois: int, salarie: Optional[models.Salarie], h: dict) -> dict:
    """`h` : hypothèses (voir SimulationIn). Les valeurs absentes sont reprises de la fiche du salarié, sinon neutres."""
    debut = date(annee, mois, 1)
    fin = date(annee, mois, calendar.monthrange(annee, mois)[1])
    nature = h.get("nature") or ("journalier" if salarie is not None and salarie.type_remuneration == "journalier" else "mensuel")
    cat, sur = h.get("salaire_categoriel"), h.get("sursalaire")
    if salarie is not None and (cat is None or sur is None):
        sal = svc_salaries.salaire_en_vigueur(salarie, fin)
        if sal is None and cat is None:
            raise ErreurPaie(f"{salarie.matricule} : aucun salaire en vigueur en {mois:02d}/{annee}.")
        if sal is not None:
            cat = sal.montant if cat is None else cat
            sur = sal.sursalaire if sur is None else sur
    if cat is None:
        raise ErreurPaie("Indiquez un salaire (ou choisissez un salarié).", 422)
    rubriques = []
    if salarie is not None and h.get("inclure_rubriques_fixes", True) and nature == "mensuel":
        rubriques += svc_fixes.rubriques_du_mois(db, salarie.id, debut, fin)
    for r in h.get("rubriques", []):
        rubriques.append(Rubrique(r["code"], r.get("libelle") or r["code"], r["type"], D(str(r["montant"]))))
    entree = EntreeBulletin(
        nature=nature, debut=debut, fin=fin,
        parts=D(str(h["parts"])) if h.get("parts") is not None else (D(salarie.nombre_parts) if salarie is not None else D(1)),
        personnes_cmu=h["personnes_cmu"] if h.get("personnes_cmu") is not None else (salarie.nombre_personnes_cmu if salarie is not None else 0),
        date_entree=h.get("date_entree") or (salarie.date_embauche if salarie is not None else None),
        salaire_categoriel=D(str(cat)), sursalaire=D(str(sur or 0)),
        jours_payes=D(str(h.get("jours_payes", 30))), jours_absence_ja=D(str(h.get("jours_absence", 0))),
        heures_absence=D(str(h.get("heures_absence", 0))),
        indemnite_transport=(salarie.indemnite_transport if salarie is not None else None),
        heures_travaillees=D(str(h.get("heures_travaillees", 0))), jours_presence=D(str(h.get("jours_presence", 0))),
        heures_sup={i: D(str(h.get(f"hs{i}", 0))) for i in (1, 2, 3, 4)},
        rubriques=tuple(rubriques),
    )
    params = charger(db, fin)
    r = calcul.calculer_bulletin(entree, params)
    cout = r.total_imposable + r.gains_non_imposables + D(r.charges_patronales["total"])
    return {
        "periode": {"debut": debut, "fin": fin, "nature": nature},
        "lignes": lignes_vers_json(r.lignes),
        "totaux": {"total_imposable": r.total_imposable, "cnps": r.cnps, "its": r.its, "gains_non_imposables": r.gains_non_imposables,
                   "retenues_non_imposables": r.retenues_non_imposables, "net_a_payer": r.net_a_payer},
        "charges_patronales": vers_json(r.charges_patronales), "cout_employeur": cout, "anomalies": r.anomalies,
    }
