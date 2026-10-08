"""Rapports de pilotage construits sur les bulletins VALIDÉS."""
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from ..core import models

D = Decimal
MOIS = ["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


def _bulletins(db: Session, annee: int, mois: Optional[int] = None):
    q = db.query(models.Bulletin, models.Campagne).join(models.Campagne, models.Campagne.id == models.Bulletin.campagne_id)\
        .filter(models.Bulletin.statut == "valide", models.Campagne.annee == annee)
    if mois:
        q = q.filter(models.Campagne.mois == mois)
    return q.all()


def _cout(b: models.Bulletin) -> Decimal:
    return b.total_imposable + b.gains_non_imposables + D(b.charges_patronales["total"])


def masse_salariale(db: Session, annee: int) -> dict:
    """Une ligne par mois : effectif payé, masse imposable, cotisations, net, coût employeur."""
    agg = defaultdict(lambda: {"salaries": set(), "imposable": D(0), "gains_ni": D(0), "cnps": D(0), "its": D(0), "net": D(0), "charges": D(0), "cout": D(0)})
    for b, c in _bulletins(db, annee):
        a = agg[c.mois]
        a["salaries"].add(b.salarie_id)
        a["imposable"] += b.total_imposable; a["gains_ni"] += b.gains_non_imposables; a["cnps"] += b.cnps; a["its"] += b.its
        a["net"] += b.net_a_payer; a["charges"] += D(b.charges_patronales["total"]); a["cout"] += _cout(b)
    entetes = ["Mois", "Effectif payé", "Salaire brut imposable", "Gains non imposables", "CNPS salarié", "ITS", "Net payé", "Charges patronales", "Coût employeur"]
    lignes, tot = [], {k: D(0) for k in entetes[2:]}
    for m in range(1, 13):
        if m not in agg:
            continue
        a = agg[m]
        l = [MOIS[m], len(a["salaries"]), a["imposable"], a["gains_ni"], a["cnps"], a["its"], a["net"], a["charges"], a["cout"]]
        lignes.append(l)
        for k, v in zip(entetes[2:], l[2:]):
            tot[k] += v
    return {"titre": f"Masse salariale {annee}", "entetes": entetes, "lignes": lignes, "totaux": tot}


def par_service(db: Session, annee: int, mois: int) -> dict:
    agg = defaultdict(lambda: {"salaries": set(), "imposable": D(0), "net": D(0), "cout": D(0)})
    for b, c in _bulletins(db, annee, mois):
        serv = (b.identite.get("service") or {}).get("libelle") or "(sans service)"
        a = agg[serv]
        a["salaries"].add(b.salarie_id); a["imposable"] += b.total_imposable; a["net"] += b.net_a_payer; a["cout"] += _cout(b)
    entetes = ["Service", "Effectif payé", "Salaire brut imposable", "Net payé", "Coût employeur"]
    lignes = [[s, len(a["salaries"]), a["imposable"], a["net"], a["cout"]] for s, a in sorted(agg.items())]
    tot = {k: sum((l[i] for l in lignes), D(0)) for i, k in enumerate(entetes) if i >= 2}
    return {"titre": f"Répartition par service {MOIS[mois]} {annee}", "entetes": entetes, "lignes": lignes, "totaux": tot}


def heures_supplementaires(db: Session, annee: int) -> dict:
    agg = defaultdict(lambda: {"h": [D(0)] * 4, "montant": D(0), "salaries": set()})
    for b, c in _bulletins(db, annee):
        hs = b.entree.get("heures_sup") or {}
        a = agg[c.mois]
        for i in range(4):
            a["h"][i] += D(str(hs.get(str(i + 1), 0)))
        montant = sum((D(l["montant"]) for l in b.lignes if l["code"] in ("HS1", "HS2", "HS3", "HS4")), D(0))
        a["montant"] += montant
        if montant:
            a["salaries"].add(b.salarie_id)
    entetes = ["Mois", "Salariés concernés", "HS1 (h)", "HS2 (h)", "HS3 (h)", "HS4 (h)", "Montant des HS"]
    lignes = [[MOIS[m], len(a["salaries"]), *a["h"], a["montant"]] for m, a in sorted(agg.items())]
    tot = {k: sum((l[i] for l in lignes), D(0)) for i, k in enumerate(entetes) if i >= 2}
    return {"titre": f"Heures supplémentaires {annee}", "entetes": entetes, "lignes": lignes, "totaux": tot}


def livre_de_paie(db: Session, annee: int, mois: int) -> dict:
    """Nominatif : une ligne par bulletin validé (données de salaire -> réservé aux droits sensibles)."""
    entetes = ["Campagne", "Matricule", "Nom et prénoms", "Service", "Salaire brut imposable", "Gains non imposables", "CNPS", "ITS", "Retenues non imposables", "Net à payer"]
    lignes = []
    for b, c in sorted(_bulletins(db, annee, mois), key=lambda x: (x[1].numero, x[0].identite["matricule"])):
        i = b.identite
        lignes.append([c.libelle, i["matricule"], f"{i['nom']} {i.get('prenoms') or ''}".strip(), (i.get("service") or {}).get("libelle", ""),
                       b.total_imposable, b.gains_non_imposables, b.cnps, b.its, b.retenues_non_imposables, b.net_a_payer])
    tot = {k: sum((l[i] for l in lignes), D(0)) for i, k in enumerate(entetes) if i >= 4}
    return {"titre": f"Livre de paie {MOIS[mois]} {annee}", "entetes": entetes, "lignes": lignes, "totaux": tot}


def effectif(db: Session, au: Optional[date] = None) -> dict:
    jour = au or date.today()
    actifs = [s for s in db.query(models.Salarie).all()
              if (s.date_embauche is None or s.date_embauche <= jour) and (s.date_sortie is None or s.date_sortie > jour)]
    def repartition(cle):
        c = defaultdict(int)
        for s in actifs:
            c[cle(s)] += 1
        return sorted(c.items(), key=lambda x: -x[1])
    def tranche(s):
        if not s.date_embauche:
            return "Non renseignée"
        ans = (jour - s.date_embauche).days / 365.25
        return "Moins de 1 an" if ans < 1 else "1 à 5 ans" if ans < 5 else "5 à 10 ans" if ans < 10 else "10 ans et plus"
    lignes = [["Total", "Effectif", len(actifs)]]
    for titre, cle in (("Service", lambda s: s.service.libelle if s.service else "(sans service)"),
                       ("Type de contrat", lambda s: s.type_contrat.libelle if s.type_contrat else "(non renseigné)"),
                       ("Rémunération", lambda s: "Journalier" if s.type_remuneration == "journalier" else "Mensuel"),
                       ("Sexe", lambda s: {"M": "Hommes", "F": "Femmes"}.get(s.sexe, "(non renseigné)")),
                       ("Ancienneté", tranche)):
        lignes += [[titre, k, n] for k, n in repartition(cle)]
    return {"titre": f"Effectif au {jour.strftime('%d/%m/%Y')}", "entetes": ["Critère", "Valeur", "Salariés"], "lignes": lignes, "totaux": {}}


def mouvements(db: Session, du: date, au: date) -> dict:
    lignes = []
    for s in db.query(models.Salarie).order_by(models.Salarie.matricule).all():
        if s.date_embauche and du <= s.date_embauche <= au:
            lignes.append([s.date_embauche, "Entrée", s.matricule, f"{s.nom} {s.prenoms or ''}".strip(), s.service.libelle if s.service else "", ""])
        if s.date_sortie and du <= s.date_sortie <= au:
            lignes.append([s.date_sortie, "Sortie", s.matricule, f"{s.nom} {s.prenoms or ''}".strip(), s.service.libelle if s.service else "", s.motif_sortie or ""])
    lignes.sort(key=lambda l: (l[0], l[2]))
    return {"titre": f"Mouvements du {du.strftime('%d/%m/%Y')} au {au.strftime('%d/%m/%Y')}",
            "entetes": ["Date", "Mouvement", "Matricule", "Nom et prénoms", "Service", "Motif"], "lignes": lignes, "totaux": {}}
