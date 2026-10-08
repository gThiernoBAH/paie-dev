"""Solde de tout compte : campagne dédiée à un salarié sortant (congés, licenciement, préavis)."""
import calendar
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core import models
from ..moteur.arrondis import centimes
from ..moteur.calcul import mois_complets
from . import conges as svc_conges
from . import parametres as param
from . import salaries as svc_salaries
from .bulletins import ErreurPaie

MOTIFS = {"demission": "Démission", "licenciement": "Licenciement", "fin_contrat": "Fin de contrat",
          "retraite": "Départ en retraite", "deces": "Décès", "autre": "Autre"}


def indemnite_licenciement(db: Session, reference_mensuelle: Decimal, anciennete_mois: int, a_la_date: date) -> Decimal:
    """Barème par tranches d'ancienneté (taux en % du salaire mensuel de référence, par année)."""
    t = lambda cle: Decimal(str(param.lire(db, cle, a_la_date)))
    l1, l2 = Decimal(str(param.lire(db, "licenciement_limite_tranche1", a_la_date))), Decimal(str(param.lire(db, "licenciement_limite_tranche2", a_la_date)))
    annees = Decimal(anciennete_mois) / 12
    a1 = min(annees, l1)
    a2 = max(Decimal(0), min(annees, l2) - l1)
    a3 = max(Decimal(0), annees - l2)
    coef = (a1 * t("licenciement_taux_tranche1") + a2 * t("licenciement_taux_tranche2") + a3 * t("licenciement_taux_tranche3")) / 100
    return centimes(reference_mensuelle * coef)


def apercu(db: Session, s: models.Salarie, date_sortie: date, motif: str) -> dict:
    salaire = svc_salaries.salaire_en_vigueur(s, date_sortie)
    if salaire is None:
        raise ErreurPaie(f"{s.matricule} : aucun salaire en vigueur à la date de sortie.")
    reference = Decimal(salaire.montant) + Decimal(salaire.sursalaire or 0)
    solde = svc_conges.solde(db, s, date_sortie)
    base_mois = Decimal(str(param.lire(db, "conges_jours_base_mensuelle", date_sortie)))
    jours = max(Decimal(0), solde["solde"])
    indemnite_conges = centimes(reference * jours / base_mois)
    anciennete = mois_complets(s.date_embauche, date_sortie) if s.date_embauche else 0
    licenciement = indemnite_licenciement(db, reference, anciennete, date_sortie) if motif == "licenciement" else Decimal(0)
    plafond = Decimal(str(param.lire(db, "licenciement_plafond", date_sortie)))
    lcn = min(licenciement, plafond)
    return {"reference_mensuelle": reference, "jours_conges": jours, "indemnite_conges": indemnite_conges,
            "anciennete_mois": anciennete, "indemnite_licenciement": licenciement,
            "licenciement_non_imposable": lcn, "licenciement_imposable": licenciement - lcn}


def creer(db: Session, s: models.Salarie, date_sortie: date, motif: str, acteur: models.Utilisateur,
          jours_conges: Optional[Decimal] = None, preavis: Optional[Decimal] = None) -> models.Campagne:
    if motif not in MOTIFS:
        raise ErreurPaie("Motif de sortie inconnu.", 422)
    if s.date_embauche and date_sortie < s.date_embauche:
        raise ErreurPaie("La date de sortie précède la date d'embauche.", 422)
    deja = db.query(models.Campagne).join(models.PresencePeriode, models.PresencePeriode.campagne_id == models.Campagne.id)\
        .filter(models.Campagne.type_campagne == "solde", models.PresencePeriode.salarie_id == s.id).first()
    if deja:
        raise ErreurPaie(f"Un solde de tout compte existe déjà pour ce salarié ({deja.libelle}).")
    a = apercu(db, s, date_sortie, motif)
    s.date_sortie, s.motif_sortie, s.est_actif = date_sortie, motif, False
    debut, fin = date(date_sortie.year, date_sortie.month, 1), date_sortie
    numero = (db.query(func.max(models.Campagne.numero)).filter_by(annee=date_sortie.year, mois=date_sortie.month).scalar() or 0) + 1
    c = models.Campagne(libelle=f"Solde de tout compte {s.matricule} – {s.nom}"[:100], type_campagne="solde", nature_bulletin="mensuel",
                        annee=date_sortie.year, mois=date_sortie.month, numero=numero, debut=debut, fin=fin, cree_par=acteur.identifiant)
    db.add(c)
    db.flush()
    jours_payes = Decimal(min(30, date_sortie.day))
    db.add(models.PresencePeriode(campagne_id=c.id, salarie_id=s.id, jours_payes=jours_payes, modifie_par=acteur.identifiant))

    def saisie(code: str, libelle: str, type_: str, montant: Decimal, quantite=None, commentaire=None):
        if montant > 0:
            db.add(models.SaisieRubrique(campagne_id=c.id, salarie_id=s.id, code=code, libelle=libelle, type=type_, montant=montant,
                                         quantite=quantite, commentaire=commentaire, origine="solde", cree_par=acteur.identifiant))

    if jours_conges is not None:
        base_mois = Decimal(str(param.lire(db, "conges_jours_base_mensuelle", date_sortie)))
        a["jours_conges"], a["indemnite_conges"] = jours_conges, centimes(a["reference_mensuelle"] * jours_conges / base_mois)
    saisie("ICP", "Indemnité compensatrice de congés payés", "GI", a["indemnite_conges"], a["jours_conges"], f"{a['jours_conges']} jour(s)")
    saisie("IPV", "Indemnité de préavis", "GI", preavis or Decimal(0))
    saisie("LCI", "Indemnité de licenciement (part imposable)", "GI", a["licenciement_imposable"])
    saisie("LCN", "Indemnité de licenciement (part non imposable)", "GN", a["licenciement_non_imposable"])
    db.flush()
    return c
