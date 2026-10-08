"""États déclaratifs (CNPS, ITS, DISA) construits à partir des bulletins VALIDÉS.

Les colonnes suivent les informations exigées par les organismes ; la mise en page officielle exacte
(gabarits CNPS / DGI) est à valider avec les modèles en vigueur -- voir docs/DECLARATIONS.md."""
from collections import OrderedDict
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from ..core import crypto, models

D = Decimal


def _bulletins(db: Session, annee: int, mois: Optional[int] = None) -> list:
    q = db.query(models.Bulletin, models.Campagne).join(models.Campagne, models.Campagne.id == models.Bulletin.campagne_id)\
        .filter(models.Bulletin.statut == "valide", models.Campagne.annee == annee)
    if mois:
        q = q.filter(models.Campagne.mois == mois)
    return q.order_by(models.Bulletin.salarie_id, models.Campagne.mois, models.Campagne.numero).all()


def _jours(b: models.Bulletin) -> Decimal:
    e = b.entree
    return D(e["jours_presence"] if e.get("nature") == "journalier" else e["jours_payes"])


def _cumuls(db: Session, annee: int, mois: Optional[int]) -> "OrderedDict[int, dict]":
    out: "OrderedDict[int, dict]" = OrderedDict()
    for b, c in _bulletins(db, annee, mois):
        a = out.setdefault(b.salarie_id, {
            "salarie_id": b.salarie_id, "identite": b.identite, "jours": D(0), "imposable": D(0), "gains_ni": D(0),
            "cnps_sal": D(0), "its": D(0), "retraite": D(0), "pf": D(0), "at": D(0), "ta": D(0), "fpc": D(0),
            "mois": set(), "net": D(0)})
        a["jours"] += _jours(b)
        a["imposable"] += b.total_imposable
        a["gains_ni"] += b.gains_non_imposables
        a["cnps_sal"] += b.cnps
        a["its"] += b.its
        a["net"] += b.net_a_payer
        ch = b.charges_patronales
        a["retraite"] += D(ch["retraite"]); a["pf"] += D(ch["prestations_familiales"]); a["at"] += D(ch["accident_travail"])
        a["ta"] += D(ch["taxe_apprentissage"]); a["fpc"] += D(ch["formation_continue"])
        a["mois"].add(c.mois)
    return out


def _nom(i: dict) -> str:
    return f"{i['nom']} {i.get('prenoms') or ''}".strip()


def _numero_cnps(db: Session, salarie_id: int) -> str:
    s = db.get(models.Salarie, salarie_id)
    return (crypto.dechiffrer(s.numero_cnps_chiffre) if s and s.numero_cnps_chiffre else "") or ""


def etat_cnps(db: Session, annee: int, mois: int, plafond: Decimal) -> dict:
    """Déclaration mensuelle des salaires et cotisations CNPS (un salarié par ligne, tous bulletins du mois cumulés)."""
    entetes = ["Matricule", "N° CNPS", "Nom et prénoms", "Date d'embauche", "Jours", "Salaire brut imposable", "Assiette retraite (plafonnée)",
               "Retraite salarié", "Retraite employeur", "Prestations familiales", "Accident du travail", "Total employeur CNPS"]
    lignes, tot = [], {k: D(0) for k in entetes[5:]}
    for a in _cumuls(db, annee, mois).values():
        i = a["identite"]
        assiette = min(a["imposable"], plafond * len(a["mois"])) if a["imposable"] > 0 else D(0)
        emp = a["retraite"] + a["pf"] + a["at"]
        l = [i["matricule"], _numero_cnps(db, a["salarie_id"]), _nom(i), (i.get("date_embauche") or "")[:10], a["jours"], a["imposable"], assiette,
             a["cnps_sal"], a["retraite"], a["pf"], a["at"], emp]
        lignes.append(l)
        for k, v in zip(entetes[5:], l[5:]):
            tot[k] += v
    return {"titre": f"CNPS {mois:02d}-{annee}", "entetes": entetes, "lignes": lignes, "totaux": tot}


def etat_its(db: Session, annee: int, mois: int) -> dict:
    entetes = ["Matricule", "Nom et prénoms", "Parts", "Salaire brut imposable", "ITS retenu"]
    lignes, tot = [], {"Salaire brut imposable": D(0), "ITS retenu": D(0)}
    for a in _cumuls(db, annee, mois).values():
        i = a["identite"]
        lignes.append([i["matricule"], _nom(i), D(str(i.get("parts", 1))), a["imposable"], a["its"]])
        tot["Salaire brut imposable"] += a["imposable"]
        tot["ITS retenu"] += a["its"]
    return {"titre": f"ITS {mois:02d}-{annee}", "entetes": entetes, "lignes": lignes, "totaux": tot}


def etat_fdfp(db: Session, annee: int, mois: int) -> dict:
    entetes = ["Matricule", "Nom et prénoms", "Masse salariale imposable", "Taxe d'apprentissage", "Formation continue"]
    lignes, tot = [], {k: D(0) for k in entetes[2:]}
    for a in _cumuls(db, annee, mois).values():
        i = a["identite"]
        l = [i["matricule"], _nom(i), a["imposable"], a["ta"], a["fpc"]]
        lignes.append(l)
        for k, v in zip(entetes[2:], l[2:]):
            tot[k] += v
    return {"titre": f"FDFP {mois:02d}-{annee}", "entetes": entetes, "lignes": lignes, "totaux": tot}


def etat_disa(db: Session, annee: int) -> dict:
    """Déclaration annuelle des salaires (DISA) : cumuls par salarié sur l'année."""
    entetes = ["Matricule", "N° CNPS", "Nom et prénoms", "Date de naissance", "Date d'embauche", "Mois travaillés", "Jours",
               "Salaire brut imposable", "Gains non imposables", "CNPS salarié", "ITS", "Net payé"]
    lignes, tot = [], {k: D(0) for k in entetes[7:]}
    for a in _cumuls(db, annee, None).values():
        i = a["identite"]
        l = [i["matricule"], _numero_cnps(db, a["salarie_id"]), _nom(i), (i.get("date_naissance") or "")[:10], (i.get("date_embauche") or "")[:10],
             len(a["mois"]), a["jours"], a["imposable"], a["gains_ni"], a["cnps_sal"], a["its"], a["net"]]
        lignes.append(l)
        for k, v in zip(entetes[7:], l[7:]):
            tot[k] += v
    return {"titre": f"DISA {annee}", "entetes": entetes, "lignes": lignes, "totaux": tot}
