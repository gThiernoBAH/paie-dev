from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

ZERO = Decimal(0)


@dataclass(frozen=True)
class ParametresPaie:
    """Toutes les valeurs légales et de paramétrage utiles au calcul, à une date donnée."""
    heures_mensuelles: Decimal
    heures_hebdo: Decimal
    # arrondis
    arrondi_cotisations: str
    arrondi_its_mensuel: str
    arrondi_its_journalier: str
    # CNPS / FDFP
    cnps_retraite_salarie: Decimal
    cnps_retraite_employeur: Decimal
    cnps_plafond_retraite: Decimal
    cnps_prestations_familiales: Decimal
    cnps_plafond_prestations_familiales: Decimal
    cnps_accident_travail: Decimal
    fdfp_taxe_apprentissage: Decimal
    fdfp_formation_continue: Decimal
    # ITS
    its_bareme: tuple          # ((borne|None, taux %), ...)
    its_ricf_demi_part: Decimal
    its_ricf_maximum: Decimal
    # CMU
    cmu_par_personne: Decimal
    # heures supplémentaires : majorations en % pour les tranches 1 à 4
    hs_majorations: tuple
    # ancienneté
    anciennete_seuil_mois: int
    anciennete_taux_par_an: Decimal
    anciennete_taux_maximum: Decimal
    # indemnités
    transport_mensuel: Decimal
    transport_journalier: Decimal
    transport_base_jours: int
    # journaliers
    journalier_taux_conges: Decimal
    journalier_taux_gratification: Decimal
    journalier_prime_precarite_mois: Decimal
    journalier_base_mensualisation: int


@dataclass(frozen=True)
class Rubrique:
    """Ligne variable apportée à la paie (prime, retenue, acompte...).

    type : GI gain imposable, GN gain non imposable, RI retenue imposable, RN retenue non imposable.
    """
    code: str
    libelle: str
    type: str
    montant: Decimal
    quantite: Optional[Decimal] = None
    taux: Optional[Decimal] = None


@dataclass(frozen=True)
class EntreeBulletin:
    nature: str                       # 'mensuel' | 'journalier'
    debut: date
    fin: date
    parts: Decimal = Decimal(1)
    personnes_cmu: int = 0
    date_entree: Optional[date] = None        # début de l'ancienneté
    salaire_categoriel: Decimal = ZERO        # montant mensuel (référence mensuelle pour un journalier)
    sursalaire: Decimal = ZERO
    # --- mensuels ---
    jours_payes: Decimal = Decimal(30)        # jours calendaires payés dans le mois (30 = mois entier)
    jours_absence_ja: Decimal = ZERO          # jours d'absence non payés (JA)
    heures_absence: Decimal = ZERO            # heures d'absence non payées (ABS)
    indemnite_transport: Optional[Decimal] = None   # montant mensuel convenu ; None = paramètre
    anciennete_active: bool = True
    # --- journaliers ---
    heures_travaillees: Decimal = ZERO
    jours_presence: Decimal = ZERO
    # --- communs ---
    heures_sup: dict = field(default_factory=dict)   # {1: h, 2: h, 3: h, 4: h}
    rubriques: tuple = ()


@dataclass
class LigneBulletin:
    code: str
    libelle: str
    type: str                 # GI GN RI RN IM TO
    quantite: Optional[Decimal] = None
    taux: Optional[Decimal] = None
    montant: Decimal = ZERO   # gain, retenue ou total selon le type


@dataclass
class ResultatBulletin:
    lignes: list
    total_imposable_brut: Decimal       # TIG
    total_retenues_imposables: Decimal  # TIR
    total_imposable: Decimal            # TI (arrondi)
    cnps: Decimal
    its: Decimal
    total_impots: Decimal               # TIP
    gains_non_imposables: Decimal       # TNG
    retenues_non_imposables: Decimal    # TNR
    net_non_imposable: Decimal          # TNI
    net_a_payer: Decimal                # NET
    charges_patronales: dict
    anomalies: list

    def ligne(self, code: str) -> Optional[LigneBulletin]:
        return next((l for l in self.lignes if l.code == code), None)
