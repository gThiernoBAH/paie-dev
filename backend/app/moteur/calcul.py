"""Calcul d'un bulletin (mensuel ou journalier). Voir la documentation des règles dans docs/MOTEUR.md."""
from datetime import date
from decimal import Decimal
from typing import Optional

from .arrondis import ZERO, appliquer_mode, centimes, d, entier_proche, entier_tronque
from .modeles import EntreeBulletin, LigneBulletin, ParametresPaie, ResultatBulletin, Rubrique

CENT = Decimal(100)
HEURES_PAR_JOUR = Decimal(8)


# ---------------------------------------------------------------------------
# Briques de calcul (publiques : réutilisées par le solde de tout compte, les simulations...)
# ---------------------------------------------------------------------------
def taux_horaire(montant_mensuel: Decimal, p: ParametresPaie) -> Decimal:
    """Taux horaire arrondi au centime, comme sur les bulletins existants (135 540 / 173,33 = 781,98)."""
    return centimes(d(montant_mensuel) / p.heures_mensuelles)


def mois_complets(debut: date, fin: date) -> int:
    """Nombre de mois révolus entre deux dates (inclusif de la fin de période)."""
    mois = (fin.year - debut.year) * 12 + (fin.month - debut.month)
    if fin.day < debut.day:
        mois -= 1
    return max(0, mois)


def taux_anciennete(date_entree: Optional[date], fin_periode: date, p: ParametresPaie) -> Decimal:
    """Pourcentage de la prime d'ancienneté : 1 %/année révolue, dès le seuil (25 mois), plafonné (25 %)."""
    if date_entree is None:
        return ZERO
    mois = mois_complets(date_entree, fin_periode)
    if mois < p.anciennete_seuil_mois:
        return ZERO
    return min(p.anciennete_taux_maximum, Decimal(mois // 12) * p.anciennete_taux_par_an)


def impot_bareme(base: Decimal, p: ParametresPaie) -> Decimal:
    """ITS brut par tranches progressives (avant réduction pour charges de famille)."""
    impot, bas = ZERO, ZERO
    for borne, taux in p.its_bareme:
        haut = base if borne is None else min(base, borne)
        if haut > bas:
            impot += (haut - bas) * taux / CENT
        if borne is None or base <= borne:
            break
        bas = borne
    return impot


def reduction_charges_famille(parts: Decimal, p: ParametresPaie) -> Decimal:
    """RICF : un montant par demi-part au-delà de la première, plafonné."""
    demi_parts = max(ZERO, (d(parts) - 1) * 2)
    return min(p.its_ricf_maximum, p.its_ricf_demi_part * entier_proche(demi_parts))


def calculer_its(total_imposable: Decimal, parts: Decimal, p: ParametresPaie, *, journalier: bool = False,
                 jours: Decimal = ZERO) -> Decimal:
    """ITS d'un bulletin.

    Mensuel : barème sur le total imposable, moins la réduction pour charges de famille.
    Journalier : « mensualisation » -- le revenu est ramené à un mois entier, taxé comme tel, puis
    l'impôt est ramené aux jours payés (cf. paramètre journalier_base_mensualisation).
    """
    if total_imposable <= 0:
        return ZERO
    ricf = reduction_charges_famille(parts, p)
    if not journalier:
        return appliquer_mode(max(ZERO, impot_bareme(total_imposable, p) - ricf), p.arrondi_its_mensuel)
    if jours <= 0:
        return ZERO
    base = Decimal(p.journalier_base_mensualisation)
    revenu_mensuel = total_imposable * base / jours
    impot_mensuel = max(ZERO, impot_bareme(revenu_mensuel, p) - ricf)
    return appliquer_mode(impot_mensuel * jours / base, p.arrondi_its_journalier)


def calculer_cnps_salarie(total_imposable: Decimal, p: ParametresPaie) -> Decimal:
    base = min(total_imposable, p.cnps_plafond_retraite)
    return appliquer_mode(max(ZERO, base) * p.cnps_retraite_salarie / CENT, p.arrondi_cotisations)


def charges_patronales(total_imposable: Decimal, p: ParametresPaie) -> dict:
    """Part employeur : sert aux déclarations et au coût du salarié (pas imprimée sur le bulletin)."""
    base_retraite = min(max(ZERO, total_imposable), p.cnps_plafond_retraite)
    base_pf = min(max(ZERO, total_imposable), p.cnps_plafond_prestations_familiales)
    res = {
        "retraite": base_retraite * p.cnps_retraite_employeur / CENT,
        "prestations_familiales": base_pf * p.cnps_prestations_familiales / CENT,
        "accident_travail": base_pf * p.cnps_accident_travail / CENT,
        "taxe_apprentissage": max(ZERO, total_imposable) * p.fdfp_taxe_apprentissage / CENT,
        "formation_continue": max(ZERO, total_imposable) * p.fdfp_formation_continue / CENT,
    }
    res = {k: appliquer_mode(v, p.arrondi_cotisations) for k, v in res.items()}
    res["total"] = sum(res.values(), ZERO)
    return res


def prime_precarite(mois: Decimal, p: ParametresPaie) -> Decimal:
    """Prime de précarité d'un journalier (non imposable) : montant par mois complet."""
    return centimes(p.journalier_prime_precarite_mois * d(mois))


# ---------------------------------------------------------------------------
# Assemblage du bulletin
# ---------------------------------------------------------------------------
def _heures_sup(entree: EntreeBulletin, taux_h: Decimal, p: ParametresPaie, lignes: list) -> Decimal:
    """Ajoute les lignes HS1..HS4 ; renvoie la valeur des HS au taux SIMPLE (base de la gratification)."""
    simple = ZERO
    for tranche in (1, 2, 3, 4):
        h = d(entree.heures_sup.get(tranche, 0))
        if h <= 0:
            continue
        maj = p.hs_majorations[tranche - 1]
        gain = centimes(h * taux_h * (CENT + maj) / CENT)
        lignes.append(LigneBulletin(f"HS{tranche}", f"Heures supplémentaires +{maj.normalize():f} %", "GI", h, taux_h, gain))
        simple += h * taux_h
    return centimes(simple)


def _mensuel(e: EntreeBulletin, p: ParametresPaie, lignes: list, anomalies: list) -> None:
    cat, sur = d(e.salaire_categoriel), d(e.sursalaire)
    jours = d(e.jours_payes)
    prorata = jours / Decimal(30)
    th_cat, th_sur = taux_horaire(cat, p), taux_horaire(sur, p)
    th_total = th_cat + th_sur

    lignes.append(LigneBulletin("JT", "Salaire de base (jours travaillés)", "GI", jours, cat, centimes(cat * prorata)))
    if sur > 0:
        lignes.append(LigneBulletin("SS", "Sursalaire", "GI", p.heures_mensuelles, th_sur, centimes(sur * prorata)))
    if e.anciennete_active:
        taux = taux_anciennete(e.date_entree, e.fin, p)
        if taux > 0:
            lignes.append(LigneBulletin("ANC", "Prime d'ancienneté", "GI", taux, cat, centimes(cat * prorata * taux / CENT)))
    _heures_sup(e, th_total, p, lignes)

    # Absences non payées : retenues imposables, valorisées au taux horaire total.
    if d(e.heures_absence) > 0:
        h = d(e.heures_absence)
        lignes.append(LigneBulletin("ABS", "Absences (heures)", "RI", h, th_total, centimes(h * th_total)))
    if d(e.jours_absence_ja) > 0:
        j = d(e.jours_absence_ja)
        lignes.append(LigneBulletin("JA", "Absences (jours)", "RI", j, th_total * HEURES_PAR_JOUR, centimes(j * HEURES_PAR_JOUR * th_total)))

    # Transport : la part jusqu'au plafond d'exonération est non imposable, l'excédent est imposable ;
    # l'une et l'autre sont proratisées sur les jours de présence.
    convenu = d(e.indemnite_transport) if e.indemnite_transport is not None else p.transport_mensuel
    if convenu > 0:
        base_jours = Decimal(p.transport_base_jours)
        presence = max(ZERO, min(base_jours, jours - d(e.jours_absence_ja)))
        exonere = min(convenu, p.transport_mensuel)
        excedent = convenu - exonere
        lignes.append(LigneBulletin("TSP", "Indemnité de transport", "GN", presence, exonere, centimes(exonere * presence / base_jours)))
        if excedent > 0:
            lignes.append(LigneBulletin("TSI", "Transport (part imposable)", "GI", presence, excedent, centimes(excedent * presence / base_jours)))


def _journalier(e: EntreeBulletin, p: ParametresPaie, lignes: list, anomalies: list) -> None:
    th = taux_horaire(e.salaire_categoriel, p)
    h = d(e.heures_travaillees)
    ht = centimes(h * th)
    lignes.append(LigneBulletin("HT", "Heures travaillées", "GI", h, th, ht))
    hs_simple = _heures_sup(e, th, p, lignes)
    hs_majorees = sum((l.montant for l in lignes if l.code.startswith("HS")), ZERO)

    gratification = centimes((ht + hs_simple) * p.journalier_taux_gratification / CENT)
    lignes.append(LigneBulletin("GRA", "Gratification", "GI", ht + hs_simple, p.journalier_taux_gratification, gratification))
    conges = centimes((ht + hs_majorees + gratification) * p.journalier_taux_conges / CENT)
    lignes.append(LigneBulletin("CON", "Indemnité de congés", "GI", None, p.journalier_taux_conges, conges))

    jours = d(e.jours_presence)
    if jours > 0:
        lignes.append(LigneBulletin("TSP", "Indemnité de transport", "GN", jours, p.transport_journalier, centimes(jours * p.transport_journalier)))


def calculer_bulletin(e: EntreeBulletin, p: ParametresPaie) -> ResultatBulletin:
    if e.nature not in ("mensuel", "journalier"):
        raise ValueError("Nature de bulletin inconnue : %s" % e.nature)
    lignes: list = []
    anomalies: list = []
    (_mensuel if e.nature == "mensuel" else _journalier)(e, p, lignes, anomalies)

    for r in e.rubriques:  # rubriques variables : gardées telles que saisies
        if r.type not in ("GI", "GN", "RI", "RN"):
            raise ValueError("Type de rubrique inconnu : %s" % r.type)
        lignes.append(LigneBulletin(r.code, r.libelle, r.type, r.quantite, r.taux, centimes(r.montant)))

    if e.personnes_cmu > 0:
        lignes.append(LigneBulletin("CMU", "CMU (part salarié)", "RN", Decimal(e.personnes_cmu), p.cmu_par_personne,
                                    centimes(p.cmu_par_personne * e.personnes_cmu)))

    tig = sum((l.montant for l in lignes if l.type == "GI"), ZERO)
    tir = sum((l.montant for l in lignes if l.type == "RI"), ZERO)
    tng = sum((l.montant for l in lignes if l.type == "GN"), ZERO)
    tnr = sum((l.montant for l in lignes if l.type == "RN"), ZERO)
    ti = entier_proche(max(ZERO, tig - tir))

    cnps = calculer_cnps_salarie(ti, p)
    its = calculer_its(ti, e.parts, p, journalier=e.nature == "journalier", jours=d(e.jours_presence))
    tip = cnps + its
    tni = tng - tnr
    net = ti - tip + tni
    if net < 0:
        anomalies.append("Net à payer négatif : les retenues dépassent les gains.")

    lignes.append(LigneBulletin("TIG", "Total gains imposables", "TO", montant=centimes(tig)))
    lignes.append(LigneBulletin("TIR", "Total retenues imposables", "TO", montant=centimes(tir)))
    lignes.append(LigneBulletin("TI", "Total imposable", "TO", montant=ti))
    lignes.append(LigneBulletin("CNP", "CNPS retraite (salarié)", "IM", ti, p.cnps_retraite_salarie, cnps))
    if its > 0:
        lignes.append(LigneBulletin("ITS", "Impôt sur traitements et salaires", "IM", ti, None, its))
    lignes.append(LigneBulletin("TIP", "Total impôts et cotisations", "IM", montant=tip))
    lignes.append(LigneBulletin("TNG", "Total gains non imposables", "TO", montant=centimes(tng)))
    lignes.append(LigneBulletin("TNR", "Total retenues non imposables", "TO", montant=centimes(tnr)))
    lignes.append(LigneBulletin("TNI", "Net non imposable", "TO", montant=centimes(tni)))
    lignes.append(LigneBulletin("NET", "Net à payer", "TO", montant=net))

    return ResultatBulletin(
        lignes=lignes, total_imposable_brut=centimes(tig), total_retenues_imposables=centimes(tir),
        total_imposable=ti, cnps=cnps, its=its, total_impots=tip, gains_non_imposables=centimes(tng),
        retenues_non_imposables=centimes(tnr), net_non_imposable=centimes(tni), net_a_payer=net,
        charges_patronales=charges_patronales(ti, p), anomalies=anomalies,
    )
