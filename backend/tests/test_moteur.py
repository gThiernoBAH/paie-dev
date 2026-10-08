"""Tests de référence du moteur : bulletins RÉELS de SIVOP (« golden tests »).

Chaque cas reprend les montants imprimés sur un bulletin existant. Les lignes sont comparées au
centime près quand le legacy calcule pareil, et les TOTAUX (TI, cotisations, net) à l'unité.
"""
from datetime import date
from decimal import Decimal as D

import pytest

from app.moteur import calcul
from app.moteur.modeles import EntreeBulletin, Rubrique
from app.moteur.parametres_paie import charger


@pytest.fixture
def p(db):
    return charger(db, date(2026, 1, 31))


def test_parametres_charges(p):
    assert p.heures_mensuelles == D("173.33") and p.cnps_retraite_salarie == D("6.3")
    assert p.its_bareme[0] == (D(75000), D(0)) and p.its_bareme[-1] == (None, D(32))
    assert p.hs_majorations == (D(15), D(50), D(75), D(100))


# --- Briques ---
@pytest.mark.parametrize("base,attendu", [
    (D(50000), D(0)), (D(75000), D(0)), (D(240000), D(26400)),
    (D(966732), D("184015.68")),                              # bulletin de mars 2024
    (D(2400000), D(26400) + D(117600) + D(384000)),
    (D(9000000), D(26400) + D(117600) + D(384000) + D(1568000) + D(320000)),
])
def test_bareme_its(p, base, attendu):
    assert calcul.impot_bareme(base, p) == attendu


@pytest.mark.parametrize("parts,attendu", [(1, 0), (1.5, 5500), (2, 11000), (3.5, 27500), (5, 44000)])
def test_ricf(p, parts, attendu):
    assert calcul.reduction_charges_famille(D(str(parts)), p) == attendu


@pytest.mark.parametrize("entree,fin,attendu", [
    (date(1988, 1, 4), date(2026, 1, 31), 25), (date(2024, 1, 1), date(2025, 12, 31), 0),
    (date(2024, 1, 1), date(2026, 1, 31), 0), (date(2024, 1, 1), date(2026, 2, 28), 2), (date(2020, 6, 15), date(2026, 6, 14), 5), (None, date(2026, 1, 31), 0),
])
def test_taux_anciennete(p, entree, fin, attendu):
    assert calcul.taux_anciennete(entree, fin, p) == attendu


def test_taux_horaire(p):
    assert calcul.taux_horaire(D(135540), p) == D("781.98")
    assert calcul.taux_horaire(D(69899), p) == D("403.27")
    assert calcul.taux_horaire(D(75000), p) == D("432.70")


# --- GT-01 : SIVOP, mars 2024, 3,5 parts ---
def test_gt01_bulletin_mars_2024(p):
    r = calcul.calculer_bulletin(EntreeBulletin(
        nature="mensuel", debut=date(2024, 3, 1), fin=date(2024, 3, 31), parts=D("3.5"), anciennete_active=False,
        salaire_categoriel=D(0), indemnite_transport=D(0),
        rubriques=(Rubrique("BRU", "Brut imposable du bulletin", "GI", D(966732)),
                   Rubrique("NIM", "Gains non imposables nets", "GN", D(19400))),
    ), p)
    assert (r.total_imposable, r.cnps, r.its, r.total_impots, r.net_a_payer) == (966732, 60904, 156516, 217420, 768712)


# --- GT-10 : matricule 000054, janvier 2026, 5 parts, 8 enfants ---
def entree_gt10():
    return EntreeBulletin(
        nature="mensuel", debut=date(2026, 1, 1), fin=date(2026, 1, 31), parts=D(5), personnes_cmu=4,
        date_entree=date(1988, 1, 4), salaire_categoriel=D(135540), sursalaire=D(69899),
        jours_payes=D(30), jours_absence_ja=D(3), heures_absence=D(4), heures_sup={1: D(3)},
        indemnite_transport=D(38102),
        rubriques=(
            Rubrique("SAL", "Rappel de salaire", "GI", D("5625.18")),
            Rubrique("PLA", "Prime", "GN", D(3029)), Rubrique("PLT", "Prime", "GN", D(1500)),
            Rubrique("AS1", "Assurance", "RN", D(8600)), Rubrique("C08", "Retenue", "RN", D(25000)),
        ))


def test_gt10_lignes(p):
    r = calcul.calculer_bulletin(entree_gt10(), p)
    attendu = {"JT": "135540", "SS": "69899", "ANC": "33885", "HS1": "4089.11", "ABS": "4741", "JA": "28446",
               "TSP": "27000", "TSI": "7291.80", "CMU": "2000"}
    for code, montant in attendu.items():
        assert abs(r.ligne(code).montant - D(montant)) <= D("0.10"), code   # le legacy diffère de quelques centimes


def test_gt10_totaux_et_net(p):
    r = calcul.calculer_bulletin(entree_gt10(), p)
    assert r.total_imposable == 223143
    assert r.cnps == 14058
    assert r.its == 0                      # 23 702,88 d'impôt brut < 44 000 de réduction (5 parts)
    assert r.gains_non_imposables == 31529 and r.retenues_non_imposables == 35600 and r.net_non_imposable == -4071
    assert r.net_a_payer == 205014


# --- GT-11 : journalier, janvier 2026, 4 jours ---
def entree_gt11():
    return EntreeBulletin(nature="journalier", debut=date(2026, 1, 1), fin=date(2026, 1, 4), parts=D(1),
                          salaire_categoriel=D(75000), heures_travaillees=D(32), jours_presence=D(4))


def test_gt11_journalier(p):
    r = calcul.calculer_bulletin(entree_gt11(), p)
    assert r.ligne("HT").montant == D("13846.40")
    assert r.ligne("GRA").montant == D("865.40")
    assert abs(r.ligne("CON").montant - D("1493.86")) <= D("0.02")
    assert r.total_imposable == 16206
    assert (r.cnps, r.its, r.total_impots) == (1020, 992, 2012)
    assert r.ligne("TSP").montant == 4000
    assert r.net_a_payer == 18194


# --- GT-12 / GT-13 : journaliers, août 2026 (heures supplémentaires) ---
def entree_aout(h1, h2, jours):
    return EntreeBulletin(nature="journalier", debut=date(2026, 8, 3), fin=date(2026, 8, 8), parts=D(1),
                          salaire_categoriel=D(75000), heures_travaillees=D(40), jours_presence=D(jours),
                          heures_sup={1: D(h1), 2: D(h2)})


@pytest.mark.parametrize("h1,h2,jours,brut,ti,cnps,tsp", [
    (6, "5.5", 6, "27820.66", 27821, 1752, 6000),     # GT-12
    (5, 0, 5, "23146.66", 23147, 1458, 5000),         # GT-13
])
def test_gt12_gt13_lignes_et_cnps(p, h1, h2, jours, brut, ti, cnps, tsp):
    r = calcul.calculer_bulletin(entree_aout(h1, h2, jours), p)
    assert abs(r.total_imposable_brut - D(brut)) <= D("0.05")
    assert r.total_imposable == ti and r.cnps == cnps and r.ligne("TSP").montant == tsp


@pytest.mark.xfail(strict=False, reason="Q30 : décompte des jours de l'ITS journalier d'août non élucidé (ITS réel 1 455 / 1 290)")
@pytest.mark.parametrize("h1,h2,jours,its,net", [(6, "5.5", 6, 1455, 30614), (5, 0, 5, 1290, 25399)])
def test_gt12_gt13_its_et_net(p, h1, h2, jours, its, net):
    r = calcul.calculer_bulletin(entree_aout(h1, h2, jours), p)
    assert r.its == its and r.net_a_payer == net


# --- Propriétés générales ---
def test_deterministe(p):
    assert calcul.calculer_bulletin(entree_gt10(), p) == calcul.calculer_bulletin(entree_gt10(), p)


def test_plafond_cnps(p):
    r = calcul.calculer_bulletin(EntreeBulletin(nature="mensuel", debut=date(2026, 1, 1), fin=date(2026, 1, 31), salaire_categoriel=D(0),
                                                indemnite_transport=D(0), anciennete_active=False,
                                                rubriques=(Rubrique("BRU", "x", "GI", D(5_000_000)),)), p)
    assert r.cnps == int(D(3375000) * D("0.063"))


def test_net_negatif_signale(p):
    r = calcul.calculer_bulletin(EntreeBulletin(nature="mensuel", debut=date(2026, 1, 1), fin=date(2026, 1, 31), salaire_categoriel=D(0),
                                                indemnite_transport=D(0), anciennete_active=False,
                                                rubriques=(Rubrique("RET", "Retenue", "RN", D(50000)),)), p)
    assert r.net_a_payer < 0 and r.anomalies


def test_charges_patronales(p):
    c = calcul.charges_patronales(D(1_000_000), p)
    assert c["retraite"] == 77000 and c["prestations_familiales"] == int(D(75000) * D("0.0575"))
    assert c["total"] == sum(v for k, v in c.items() if k != "total")


def test_jours_partiels_proratises(p):
    r = calcul.calculer_bulletin(EntreeBulletin(nature="mensuel", debut=date(2026, 1, 16), fin=date(2026, 1, 31), salaire_categoriel=D(150000),
                                                jours_payes=D(15), anciennete_active=False), p)
    assert r.ligne("JT").montant == 75000
    assert r.ligne("TSP").montant == 15000     # transport proratisé sur 15 jours
