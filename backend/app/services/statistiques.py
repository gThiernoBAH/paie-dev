"""Statistiques du tableau de bord.

Trois blocs, chacun protégé par ses propres droits côté API :
  - effectifs  : fiches des salariés (sexe, âge, ancienneté, contrat, service…) ;
  - masse      : bulletins VALIDÉS de l'année (brut, net, charges, coût employeur, heures sup…) ;
  - previsionnel : coût annuel projeté à partir des salaires en vigueur (successeur de « spSalValue » du legacy).
Chaque série est livrée sous la forme {"labels": [...], "valeurs": [...]} directement exploitable par un graphique.
"""
import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core import models
from ..moteur import calcul
from ..moteur.modeles import EntreeBulletin
from ..moteur.parametres_paie import charger
from . import salaries as svc_salaries

D = Decimal
MOIS_COURTS = ["Janv.", "Févr.", "Mars", "Avr.", "Mai", "Juin", "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc."]
NON_RENSEIGNE = "Non renseigné"
TYPES_ABSENCE = {"annuel": "Congés annuels", "exceptionnel": "Permissions exceptionnelles", "maladie": "Maladies",
                 "maternite": "Maternités", "sans_solde": "Sans solde"}


def _serie(paires, limite: Optional[int] = None) -> dict:
    """[(libellé, valeur)] -> série. Les valeurs sont des nombres JSON ; `limite` garde les plus grandes."""
    paires = list(paires)
    if limite:
        paires = sorted(paires, key=lambda p: -float(p[1]))[:limite]
    return {"labels": [str(p[0]) for p in paires], "valeurs": [float(p[1]) for p in paires]}


def _compter(valeurs) -> list:
    c = defaultdict(int)
    for v in valeurs:
        c[v] += 1
    return sorted(c.items(), key=lambda x: (-x[1], str(x[0])))


def _age(naissance: Optional[date], jour: date) -> Optional[int]:
    if naissance is None:
        return None
    return jour.year - naissance.year - ((jour.month, jour.day) < (naissance.month, naissance.day))


def tranche_age(age: Optional[int]) -> str:
    """Tranches continues et exclusives (le legacy laissait de côté les salariés de 25, 35 et 45 ans)."""
    if age is None:
        return NON_RENSEIGNE
    if age <= 25:
        return "25 ans et moins"
    if age <= 35:
        return "26-35 ans"
    if age <= 45:
        return "36-45 ans"
    return "46 ans et plus"


ORDRE_AGE = ["25 ans et moins", "26-35 ans", "36-45 ans", "46 ans et plus", NON_RENSEIGNE]
ORDRE_ANCIENNETE = ["Moins de 1 an", "1 à 5 ans", "5 à 10 ans", "10 ans et plus", NON_RENSEIGNE]


def _tranche_anciennete(embauche: Optional[date], jour: date) -> str:
    if embauche is None:
        return NON_RENSEIGNE
    ans = (jour - embauche).days / 365.25
    return "Moins de 1 an" if ans < 1 else "1 à 5 ans" if ans < 5 else "5 à 10 ans" if ans < 10 else "10 ans et plus"


def _ordonner(compteurs: list, ordre: list) -> list:
    d = dict(compteurs)
    return [(k, d[k]) for k in ordre if k in d]


# ----------------------------------------------------------------- effectifs
def effectifs(db: Session, annee: int, service_id: Optional[int] = None, jour: Optional[date] = None) -> dict:
    jour = jour or date.today()
    tous = db.query(models.Salarie).all()
    actifs = [s for s in tous if (s.date_embauche is None or s.date_embauche <= jour) and (s.date_sortie is None or s.date_sortie > jour)
              and (service_id is None or s.service_id == service_id)]
    lib = lambda r, defaut="(non renseigné)": r.libelle if r is not None else defaut
    sexes = _compter({"M": "Hommes", "F": "Femmes"}.get(s.sexe, NON_RENSEIGNE) for s in actifs)
    ages = [a for a in (_age(s.date_naissance, jour) for s in actifs) if a is not None]
    anciennetes = [(jour - s.date_embauche).days / 365.25 for s in actifs if s.date_embauche]
    entrees = [s for s in tous if s.date_embauche and s.date_embauche.year == annee and (service_id is None or s.service_id == service_id)]
    sorties = [s for s in tous if s.date_sortie and s.date_sortie.year == annee and (service_id is None or s.service_id == service_id)]
    absences = defaultdict(float)
    for c in db.query(models.Conge).filter(models.Conge.statut == "approuve", func.extract("year", models.Conge.debut) == annee).all():
        if service_id is None or c.salarie.service_id == service_id:
            absences[c.type_conge] += float(c.jours_ouvrables)
    return {
        "au": jour,
        "kpi": {
            "effectif": len(actifs),
            "age_moyen": round(sum(ages) / len(ages), 1) if ages else None,
            "anciennete_moyenne": round(sum(anciennetes) / len(anciennetes), 1) if anciennetes else None,
            "entrees": len(entrees), "sorties": len(sorties),
            "taux_depart": round(100 * len(sorties) / len(actifs), 1) if actifs else None,
        },
        "sexe": _serie(sexes),
        "tranches_age": _serie(_ordonner(_compter(tranche_age(_age(s.date_naissance, jour)) for s in actifs), ORDRE_AGE)),
        "anciennete": _serie(_ordonner(_compter(_tranche_anciennete(s.date_embauche, jour) for s in actifs), ORDRE_ANCIENNETE)),
        "type_contrat": _serie(_compter(lib(s.type_contrat) for s in actifs)),
        "type_remuneration": _serie(_compter({"journalier": "Journaliers", "mensuel": "Mensuels"}.get(s.type_remuneration, s.type_remuneration) for s in actifs)),
        "services": _serie(_compter(lib(s.service, "(sans service)") for s in actifs), 15),
        "sections": _serie(_compter(lib(s.section, "(sans section)") for s in actifs), 15),
        "emplois": _serie(_compter(lib(s.emploi, "(sans emploi)") for s in actifs), 15),
        "categories": _serie(_compter(lib(s.categorie, "(sans catégorie)") for s in actifs), 15),
        "absences": _serie([(TYPES_ABSENCE.get(k, k), v) for k, v in sorted(absences.items())]),
    }


# ----------------------------------------------------------------- masse salariale (réalisé)
def _bulletins_annee(db: Session, annee: int, service_code: Optional[str]):
    q = db.query(models.Bulletin, models.Campagne).join(models.Campagne, models.Campagne.id == models.Bulletin.campagne_id)\
        .filter(models.Bulletin.statut == "valide", models.Campagne.annee == annee)
    out = []
    for b, c in q.all():
        if service_code and ((b.identite.get("service") or {}).get("code") != service_code):
            continue
        out.append((b, c))
    return out


def _cout(b: models.Bulletin) -> Decimal:
    return b.total_imposable + b.gains_non_imposables + D(b.charges_patronales["total"])


def masse(db: Session, annee: int, service_id: Optional[int] = None) -> dict:
    code = None
    if service_id:
        r = db.get(models.Referentiel, service_id)
        code = r.code if r is not None else None
    lignes = _bulletins_annee(db, annee, code)
    mois = {m: {"salaries": set(), "brut": D(0), "net": D(0), "cout": D(0), "charges": D(0), "hs": D(0)} for m in range(1, 13)}
    par = {k: defaultdict(lambda: {"net": D(0), "cout": D(0)}) for k in ("service", "emploi", "categorie", "section", "nature")}
    total = {"net": D(0), "cnps": D(0), "its": D(0), "autres_retenues": D(0), "charges": D(0), "brut": D(0), "cout": D(0)}
    sections = {s.id: (s.section.libelle if s.section else "(sans section)") for s in db.query(models.Salarie).all()}
    for b, c in lignes:
        a = mois[c.mois]
        cout = _cout(b)
        a["salaries"].add(b.salarie_id)
        a["brut"] += b.total_imposable
        a["net"] += b.net_a_payer
        a["cout"] += cout
        a["charges"] += D(b.charges_patronales["total"])
        a["hs"] += sum((D(l["montant"]) for l in b.lignes if l["code"] in ("HS1", "HS2", "HS3", "HS4")), D(0))
        ident = b.identite
        for nom, etiquette in (
            ("service", (ident.get("service") or {}).get("libelle") or "(sans service)"),
            ("emploi", (ident.get("emploi") or {}).get("libelle") or "(sans emploi)"),
            ("categorie", (ident.get("categorie") or {}).get("libelle") or "(sans catégorie)"),
            ("section", sections.get(b.salarie_id, "(sans section)")),
            ("nature", {"journalier": "Journaliers", "mensuel": "Mensuels"}.get(ident.get("type_remuneration"), "Autres")),
        ):
            par[nom][etiquette]["net"] += b.net_a_payer
            par[nom][etiquette]["cout"] += cout
        total["net"] += b.net_a_payer
        total["cnps"] += b.cnps
        total["its"] += b.its
        total["autres_retenues"] += b.retenues_non_imposables
        total["charges"] += D(b.charges_patronales["total"])
        total["brut"] += b.total_imposable
        total["cout"] += cout
    paies = [m for m in range(1, 13) if mois[m]["salaries"]]
    serie_mois = lambda cle: {"labels": MOIS_COURTS, "valeurs": [float(mois[m][cle]) for m in range(1, 13)]}
    trimestres = [sum((mois[m]["cout"] for m in range(3 * t + 1, 3 * t + 4)), D(0)) for t in range(4)]
    dernier = paies[-1] if paies else None
    return {
        "annee": annee,
        "kpi": {
            "net_total": float(total["net"]), "cout_total": float(total["cout"]), "brut_total": float(total["brut"]),
            "mois_payes": len(paies), "bulletins": len(lignes),
            "cout_moyen_par_salarie": (float(mois[dernier]["cout"] / len(mois[dernier]["salaries"])) if dernier else None),
            "brut_moyen_par_salarie": (float(mois[dernier]["brut"] / len(mois[dernier]["salaries"])) if dernier else None),
        },
        "evolution": {"labels": MOIS_COURTS, "brut": serie_mois("brut")["valeurs"], "net": serie_mois("net")["valeurs"],
                      "cout": serie_mois("cout")["valeurs"]},
        "effectif_paye": {"labels": MOIS_COURTS, "valeurs": [len(mois[m]["salaries"]) for m in range(1, 13)]},
        "heures_sup": serie_mois("hs"),
        "trimestres": {"labels": ["T1", "T2", "T3", "T4"], "valeurs": [float(t) for t in trimestres]},
        "decomposition": _serie([("Net payé", total["net"]), ("CNPS salarié", total["cnps"]), ("ITS", total["its"]),
                                 ("Autres retenues", total["autres_retenues"]), ("Charges patronales", total["charges"])]),
        "par_service": _paire(par["service"], 15),
        "par_emploi": _paire(par["emploi"], 15),
        "par_categorie": _paire(par["categorie"], 15),
        "par_section": _paire(par["section"], 15),
        "par_nature": _paire(par["nature"], 6),
        "prets": _prets(db),
    }


def _paire(groupe: dict, limite: int) -> dict:
    tri = sorted(groupe.items(), key=lambda x: -x[1]["cout"])[:limite]
    return {"labels": [k for k, _ in tri], "net": [float(v["net"]) for _, v in tri], "cout": [float(v["cout"]) for _, v in tri]}


def _prets(db: Session) -> dict:
    from . import prets as svc_prets
    actifs = db.query(models.Pret).filter(models.Pret.statut == "actif").all()
    clotures = db.query(models.Pret).filter(models.Pret.statut == "cloture").all()
    return {"encours": float(sum((svc_prets.reste_a_rembourser(p) for p in actifs), D(0))), "prets_actifs": len(actifs),
            "abandonne": float(sum((svc_prets.montant_abandonne(p) for p in clotures), D(0)))}


# ----------------------------------------------------------------- prévisionnel
def previsionnel(db: Session, service_id: Optional[int] = None, jour: Optional[date] = None) -> dict:
    """Coût employeur mensuel puis annuel (× 12) des salariés MENSUELS en activité, au barème en vigueur.

    Calculé par le moteur de paie sur un mois entier, sans absence ni heures supplémentaires, avec les
    rubriques fixes du salarié. Les journaliers (paie à l'heure) sont comptés à part, non chiffrés."""
    from .rubriques_fixes import rubriques_du_mois   # import tardif : module facultatif côté tests unitaires
    jour = jour or date.today()
    debut = date(jour.year, jour.month, 1)
    fin = date(jour.year, jour.month, calendar.monthrange(jour.year, jour.month)[1])
    params = charger(db, fin)
    groupes = defaultdict(lambda: {"salaries": 0, "mensuel": D(0)})
    sans_salaire, journaliers = 0, 0
    total = D(0)
    for s in db.query(models.Salarie).all():
        if (s.date_embauche and s.date_embauche > jour) or (s.date_sortie and s.date_sortie <= jour):
            continue
        if service_id is not None and s.service_id != service_id:
            continue
        if s.type_remuneration == "journalier":
            journaliers += 1
            continue
        sal = svc_salaries.salaire_en_vigueur(s, fin)
        if sal is None:
            sans_salaire += 1
            continue
        entree = EntreeBulletin(
            nature="mensuel", debut=debut, fin=fin, parts=D(s.nombre_parts), personnes_cmu=s.nombre_personnes_cmu,
            date_entree=s.date_embauche, salaire_categoriel=D(sal.montant), sursalaire=D(sal.sursalaire or 0),
            indemnite_transport=s.indemnite_transport, rubriques=tuple(rubriques_du_mois(db, s.id, debut, fin)))
        r = calcul.calculer_bulletin(entree, params)
        cout = r.total_imposable + r.gains_non_imposables + D(r.charges_patronales["total"])
        g = groupes[s.service.libelle if s.service else "(sans service)"]
        g["salaries"] += 1
        g["mensuel"] += cout
        total += cout
    par_service = sorted(groupes.items(), key=lambda x: -x[1]["mensuel"])[:15]
    return {
        "au": jour,
        "kpi": {"cout_mensuel": float(total), "cout_annuel": float(total * 12), "salaries_chiffres": sum(g["salaries"] for g in groupes.values()),
                "journaliers_non_chiffres": journaliers, "sans_salaire": sans_salaire},
        "par_service": {"labels": [k for k, _ in par_service], "mensuel": [float(v["mensuel"]) for _, v in par_service],
                        "annuel": [float(v["mensuel"] * 12) for _, v in par_service]},
    }
