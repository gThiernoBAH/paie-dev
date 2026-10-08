"""Construit les ParametresPaie en vigueur à une date, depuis les paramètres de la base."""
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from ..services import parametres as p
from .modeles import ParametresPaie


def charger(db: Session, a_la_date: Optional[date] = None) -> ParametresPaie:
    def v(cle):
        return p.lire(db, cle, a_la_date)

    bareme = tuple((t["jusqu_a"], t["taux"]) for t in v("its_bareme_mensuel"))
    return ParametresPaie(
        heures_mensuelles=v("heures_mensuelles"), heures_hebdo=v("heures_hebdo"),
        arrondi_cotisations=v("mode_arrondi_cotisations"), arrondi_its_mensuel=v("arrondi_its_mensuel"),
        arrondi_its_journalier=v("arrondi_its_journalier"),
        cnps_retraite_salarie=v("cnps_taux_retraite_salarie"), cnps_retraite_employeur=v("cnps_taux_retraite_employeur"),
        cnps_plafond_retraite=v("cnps_plafond_retraite"),
        cnps_prestations_familiales=v("cnps_taux_prestations_familiales"),
        cnps_plafond_prestations_familiales=v("cnps_plafond_prestations_familiales"),
        cnps_accident_travail=v("cnps_taux_accident_travail"),
        fdfp_taxe_apprentissage=v("fdfp_taux_taxe_apprentissage"), fdfp_formation_continue=v("fdfp_taux_formation_continue"),
        its_bareme=bareme, its_ricf_demi_part=v("its_ricf_par_demi_part"), its_ricf_maximum=v("its_ricf_maximum"),
        cmu_par_personne=v("cmu_montant_par_personne"),
        hs_majorations=tuple(v(f"hs_taux_tranche{i}") for i in (1, 2, 3, 4)),
        anciennete_seuil_mois=v("anciennete_seuil_mois"), anciennete_taux_par_an=v("anciennete_taux_par_an"),
        anciennete_taux_maximum=v("anciennete_taux_maximum"),
        transport_mensuel=v("transport_mensuel"), transport_journalier=v("transport_journalier"),
        transport_base_jours=v("transport_base_jours"),
        journalier_taux_conges=v("journalier_taux_conges"), journalier_taux_gratification=v("journalier_taux_gratification"),
        journalier_prime_precarite_mois=v("journalier_prime_precarite_mois"),
        journalier_base_mensualisation=v("journalier_base_mensualisation"),
    )
