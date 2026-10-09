"""Rapports de pilotage construits sur les bulletins VALIDÉS."""
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
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


# ----------------------------------------------------------------- listes et journaux (reprise des états du legacy)
def _nom_complet(s: models.Salarie) -> str:
    return f"{s.nom} {s.prenoms or ''}".strip()


def liste_personnel(db: Session, au: Optional[date] = None, inclure_sortis: bool = False) -> dict:
    """Liste nominative du personnel (sans montant)."""
    jour = au or date.today()
    entetes = ["Matricule", "Nom et prénoms", "Service", "Section", "Emploi", "Catégorie", "Type de contrat", "Rémunération",
               "Date d'embauche", "Ancienneté (ans)", "Statut"]
    lignes = []
    for s in db.query(models.Salarie).order_by(models.Salarie.matricule).all():
        en_activite = (s.date_embauche is None or s.date_embauche <= jour) and (s.date_sortie is None or s.date_sortie > jour)
        if not en_activite and not inclure_sortis:
            continue
        anciennete = round((jour - s.date_embauche).days / 365.25, 1) if s.date_embauche and s.date_embauche <= jour else ""
        lib = lambda r: r.libelle if r else ""
        lignes.append([s.matricule, _nom_complet(s), lib(s.service), lib(s.section), lib(s.emploi), lib(s.categorie), lib(s.type_contrat),
                       "Journalier" if s.type_remuneration == "journalier" else "Mensuel", s.date_embauche or "", anciennete,
                       "En activité" if en_activite else "Sorti"])
    return {"titre": f"Liste du personnel au {jour.strftime('%d/%m/%Y')}", "entetes": entetes, "lignes": lignes, "totaux": {}}


def situation_famille(db: Session, au: Optional[date] = None) -> dict:
    """Situation familiale, parts fiscales et personnes à charge (base de la CMU et de l'ITS)."""
    jour = au or date.today()
    entetes = ["Matricule", "Nom et prénoms", "Situation", "Enfants à charge", "Parts fiscales", "Personnes CMU", "Détail des enfants"]
    libelles = {"celibataire": "Célibataire", "marie": "Marié(e)", "divorce": "Divorcé(e)", "veuf": "Veuf(ve)"}
    enfants = defaultdict(list)
    for e in db.query(models.EnfantSalarie).filter_by(a_charge=True).order_by(models.EnfantSalarie.date_naissance).all():
        age = (jour.year - e.date_naissance.year - ((jour.month, jour.day) < (e.date_naissance.month, e.date_naissance.day))) if e.date_naissance else None
        enfants[e.salarie_id].append(f"{e.prenoms or e.nom} ({'?' if age is None else str(age) + ' ans'})")
    lignes = []
    for s in db.query(models.Salarie).order_by(models.Salarie.matricule).all():
        if (s.date_sortie and s.date_sortie <= jour) or (s.date_embauche and s.date_embauche > jour):
            continue
        lignes.append([s.matricule, _nom_complet(s), libelles.get(s.situation_matrimoniale, s.situation_matrimoniale), s.nombre_enfants,
                       s.nombre_parts, s.nombre_personnes_cmu, ", ".join(enfants.get(s.id, []))])
    return {"titre": f"Situation de famille au {jour.strftime('%d/%m/%Y')}", "entetes": entetes, "lignes": lignes, "totaux": {}}


def journal_rubriques(db: Session, annee: int, mois: int) -> dict:
    """Journal des rubriques variables et fixes d'un mois (nominatif, montants : droit sensible)."""
    entetes = ["Campagne", "Matricule", "Nom et prénoms", "Code", "Libellé", "Type", "Origine", "Quantité", "Montant"]
    lignes = []
    q = db.query(models.SaisieRubrique, models.Campagne, models.Salarie)\
        .join(models.Campagne, models.Campagne.id == models.SaisieRubrique.campagne_id)\
        .join(models.Salarie, models.Salarie.id == models.SaisieRubrique.salarie_id)\
        .filter(models.Campagne.annee == annee, models.Campagne.mois == mois)\
        .order_by(models.Campagne.numero, models.Salarie.matricule, models.SaisieRubrique.id)
    for s, c, sal in q.all():
        lignes.append([c.libelle, sal.matricule, _nom_complet(sal), s.code, s.libelle, s.type, s.origine, s.quantite if s.quantite is not None else "", s.montant])
    tot = {"Montant": sum((l[8] for l in lignes), D(0))}
    return {"titre": f"Journal des rubriques {MOIS[mois]} {annee}", "entetes": entetes, "lignes": lignes, "totaux": tot}


def journal_presences(db: Session, annee: int, mois: int) -> dict:
    entetes = ["Campagne", "Matricule", "Nom et prénoms", "Jours payés", "Jours de présence", "Heures travaillées", "Absences (jours)",
               "Absences (heures)", "HS1", "HS2", "HS3", "HS4"]
    lignes = []
    q = db.query(models.PresencePeriode, models.Campagne, models.Salarie)\
        .join(models.Campagne, models.Campagne.id == models.PresencePeriode.campagne_id)\
        .join(models.Salarie, models.Salarie.id == models.PresencePeriode.salarie_id)\
        .filter(models.Campagne.annee == annee, models.Campagne.mois == mois)\
        .order_by(models.Campagne.numero, models.Salarie.matricule)
    for p, c, s in q.all():
        lignes.append([c.libelle, s.matricule, _nom_complet(s), p.jours_payes, p.jours_presence, p.heures_travaillees, p.jours_absence_ja,
                       p.heures_absence, p.hs1, p.hs2, p.hs3, p.hs4])
    tot = {e: sum((l[i] for l in lignes), D(0)) for i, e in enumerate(entetes) if i >= 3}
    return {"titre": f"Journal des présences {MOIS[mois]} {annee}", "entetes": entetes, "lignes": lignes, "totaux": tot}


def journal_conges(db: Session, annee: int) -> dict:
    entetes = ["Matricule", "Nom et prénoms", "Type", "Du", "Au", "Jours ouvrables", "Statut", "Motif"]
    types = {"annuel": "Congé annuel", "exceptionnel": "Permission exceptionnelle", "maladie": "Maladie", "maternite": "Maternité", "sans_solde": "Sans solde"}
    statuts = {"demande": "À traiter", "approuve": "Approuvé", "refuse": "Refusé", "annule": "Annulé"}
    lignes = []
    for c in db.query(models.Conge).filter(func.extract("year", models.Conge.debut) == annee).order_by(models.Conge.debut).all():
        lignes.append([c.salarie.matricule, _nom_complet(c.salarie), types.get(c.type_conge, c.type_conge), c.debut, c.fin, c.jours_ouvrables,
                       statuts.get(c.statut, c.statut), c.motif or ""])
    tot = {"Jours ouvrables": sum((l[5] for l in lignes if l[6] == "Approuvé"), D(0))}
    return {"titre": f"Journal des congés et absences {annee}", "entetes": entetes, "lignes": lignes, "totaux": tot}


def journal_prets(db: Session) -> dict:
    """État des prêts et avances : remboursé, reste dû, abandonné (nominatif, montants)."""
    from . import prets as svc_prets
    entetes = ["Matricule", "Nom et prénoms", "Libellé", "Type", "Montant", "Remboursé", "Reste dû", "Abandonné", "Statut", "Clôture"]
    statuts = {"actif": "En cours", "solde": "Soldé", "annule": "Annulé", "cloture": "Clôturé"}
    lignes = []
    for p in db.query(models.Pret).order_by(models.Pret.id).all():
        cloture = ""
        if p.statut == "cloture":
            cloture = f"{svc_prets.MOTIFS_CLOTURE.get(p.motif_cloture, p.motif_cloture)} – {svc_prets.ISSUES.get(p.issue_cloture, p.issue_cloture)}"
        lignes.append([p.salarie.matricule, _nom_complet(p.salarie), p.libelle, "Avance" if p.type_pret == "avance" else "Prêt", p.montant,
                       svc_prets.montant_regle(p), svc_prets.reste_a_rembourser(p), svc_prets.montant_abandonne(p), statuts.get(p.statut, p.statut), cloture])
    tot = {e: sum((l[i] for l in lignes), D(0)) for i, e in enumerate(entetes) if i in (4, 5, 6, 7)}
    return {"titre": "État des prêts et avances", "entetes": entetes, "lignes": lignes, "totaux": tot}


def bulletins_a_controler(db: Session, annee: int, mois: int) -> dict:
    """Bulletins non validés du mois, avec leurs anomalies : à lire avant de valider une campagne."""
    entetes = ["Campagne", "Statut campagne", "Matricule", "Nom et prénoms", "Net à payer", "Anomalies"]
    statuts = {"ouverte": "Ouverte", "calculee": "Calculée", "validee": "Validée", "cloturee": "Clôturée"}
    lignes = []
    q = db.query(models.Bulletin, models.Campagne).join(models.Campagne, models.Campagne.id == models.Bulletin.campagne_id)\
        .filter(models.Campagne.annee == annee, models.Campagne.mois == mois, models.Bulletin.statut != "valide")\
        .order_by(models.Campagne.numero, models.Bulletin.id)
    for b, c in q.all():
        i = b.identite
        lignes.append([c.libelle, statuts.get(c.statut, c.statut), i["matricule"], f"{i['nom']} {i.get('prenoms') or ''}".strip(), b.net_a_payer, " ".join(b.anomalies)])
    return {"titre": f"Bulletins à contrôler {MOIS[mois]} {annee}", "entetes": entetes, "lignes": lignes, "totaux": {}}


def cumuls_annuels(db: Session, annee: int) -> dict:
    """Cumuls de l'année par salarié (bulletins validés) : jours, brut imposable, CNPS, ITS, net, coût employeur."""
    entetes = ["Matricule", "Nom et prénoms", "Mois payés", "Brut imposable", "Gains non imposables", "CNPS salarié", "ITS", "Net payé", "Coût employeur"]
    par = defaultdict(lambda: {"nom": "", "mois": set(), "brut": D(0), "gni": D(0), "cnps": D(0), "its": D(0), "net": D(0), "cout": D(0)})
    for b, c in _bulletins(db, annee):
        a = par[b.identite["matricule"]]
        a["nom"] = f"{b.identite['nom']} {b.identite.get('prenoms') or ''}".strip()
        a["mois"].add(c.mois)
        a["brut"] += b.total_imposable; a["gni"] += b.gains_non_imposables; a["cnps"] += b.cnps; a["its"] += b.its
        a["net"] += b.net_a_payer; a["cout"] += _cout(b)
    lignes = [[m, a["nom"], len(a["mois"]), a["brut"], a["gni"], a["cnps"], a["its"], a["net"], a["cout"]] for m, a in sorted(par.items())]
    tot = {e: sum((l[i] for l in lignes), D(0)) for i, e in enumerate(entetes) if i >= 3}
    return {"titre": f"Cumuls annuels {annee}", "entetes": entetes, "lignes": lignes, "totaux": tot}
