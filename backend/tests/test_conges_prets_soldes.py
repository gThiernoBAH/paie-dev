from decimal import Decimal as D

import pytest
from sqlalchemy import text

from tests.conftest import connexion, creer_compte


@pytest.fixture
def admin(client, db):
    creer_compte(db)
    return connexion(client)


def nouveau(client, h, matricule="10", embauche="2020-01-01", **plus):
    r = client.post("/salaries", headers=h, json={"nom": "DIALLO", "prenoms": "Ali", "matricule": matricule, "date_embauche": embauche,
                                                  "salaire_base": 200000, "sursalaire": 50000, **plus})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def tout_confirmer(db):
    db.execute(text("UPDATE valeurs_parametres SET statut = 'confirme'"))
    db.commit()


# ---------------------------------------------------------------- congés
def test_jours_ouvrables_hors_dimanche_et_feries(client, admin):
    sid = nouveau(client, admin)
    # semaine du lundi 2 au samedi 7 mars 2026 = 6 jours ouvrables ; le dimanche 8 est exclu
    r = client.post("/conges", headers=admin, json={"salarie_id": sid, "debut": "2026-03-02", "fin": "2026-03-08"})
    assert r.status_code == 201 and D(str(r.json()["jours_ouvrables"])) == 6
    # 1er mai 2026 (férié, vendredi) retiré
    r = client.post("/conges", headers=admin, json={"salarie_id": sid, "debut": "2026-04-27", "fin": "2026-05-02"})
    assert D(str(r.json()["jours_ouvrables"])) == 5


def test_solde_acquis_et_approbation(client, admin):
    sid = nouveau(client, admin, embauche="2025-01-01")
    solde = client.get("/conges/soldes", headers=admin).json()[0]
    assert float(solde["solde"]) > 20                                  # ~2,2 j × mois complets
    c = client.post("/conges", headers=admin, json={"salarie_id": sid, "debut": "2026-03-02", "fin": "2026-03-07"}).json()
    assert client.post(f"/conges/{c['id']}/decision", headers=admin, json={"decision": "approuver"}).json()["statut"] == "approuve"
    apres = client.get("/conges/soldes", headers=admin).json()[0]
    assert D(str(apres["pris"])) == 6
    # chevauchement refusé
    assert client.post("/conges", headers=admin, json={"salarie_id": sid, "debut": "2026-03-05", "fin": "2026-03-10"}).status_code == 409


def test_approbation_refusee_si_solde_insuffisant(client, admin):
    sid = nouveau(client, admin, embauche="2026-02-01")
    c = client.post("/conges", headers=admin, json={"salarie_id": sid, "debut": "2026-03-02", "fin": "2026-03-28"}).json()
    r = client.post(f"/conges/{c['id']}/decision", headers=admin, json={"decision": "approuver"})
    assert r.status_code == 409 and "Solde insuffisant" in r.json()["detail"]


def test_solde_initial_de_reprise(client, admin):
    sid = nouveau(client, admin, embauche="2010-01-01")
    r = client.put(f"/salaries/{sid}/solde-conges", headers=admin, json={"solde_initial": 12, "date_reference": "2026-01-01"})
    assert r.status_code == 200 and D(str(r.json()["initial"])) == 12


# ---------------------------------------------------------------- prêts
def test_pret_echeancier_et_prelevement_sur_la_paie(client, db, admin):
    sid = nouveau(client, admin)
    r = client.post("/prets", headers=admin, json={"salarie_id": sid, "libelle": "Prêt scolaire", "montant": 100000,
                                                   "nombre_echeances": 3, "annee_debut": 2026, "mois_debut": 2})
    assert r.status_code == 201, r.text
    ech = r.json()["echeances"]
    assert [float(e["montant"]) for e in ech] == [33333, 33333, 33334] and (ech[2]["annee"], ech[2]["mois"]) == (2026, 4)
    # janvier : rien à prélever
    c1 = client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 1}).json()
    client.post(f"/campagnes/{c1['id']}/initialiser", headers=admin)
    client.post(f"/campagnes/{c1['id']}/calculer", headers=admin)
    assert client.get(f"/campagnes/{c1['id']}/saisies", headers=admin).json() == []
    # février : une échéance
    c2 = client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 2}).json()
    client.post(f"/campagnes/{c2['id']}/initialiser", headers=admin)
    client.post(f"/campagnes/{c2['id']}/calculer", headers=admin)
    s = client.get(f"/campagnes/{c2['id']}/saisies", headers=admin).json()
    assert len(s) == 1 and s[0]["code"] == "PRE" and float(s[0]["montant"]) == 33333 and s[0]["origine"] == "pret"
    client.post(f"/campagnes/{c2['id']}/calculer", headers=admin)                       # idempotent
    s = client.get(f"/campagnes/{c2['id']}/saisies", headers=admin).json()
    assert len(s) == 1
    # une saisie issue d'un module ne se supprime pas à la main
    assert client.delete(f"/campagnes/{c2['id']}/saisies/{s[0]['id']}", headers=admin).status_code == 409
    # validation -> échéance prélevée ; réouverture -> à nouveau prévue
    tout_confirmer(db)
    client.post(f"/campagnes/{c1['id']}/valider", headers=admin)
    assert client.post(f"/campagnes/{c2['id']}/valider", headers=admin).status_code == 200
    pret = client.get(f"/prets/{r.json()['id']}", headers=admin).json()
    assert pret["echeances"][0]["statut"] == "prelevee" and float(pret["reste"]) == 66667
    client.post(f"/campagnes/{c2['id']}/rouvrir", headers=admin, json={"motif": "Contrôle des prélèvements"})
    assert client.get(f"/prets/{r.json()['id']}", headers=admin).json()["echeances"][0]["statut"] == "prevue"


def test_annulation_pret(client, admin):
    sid = nouveau(client, admin)
    p = client.post("/prets", headers=admin, json={"salarie_id": sid, "libelle": "Avance", "type_pret": "avance", "montant": 50000,
                                                   "nombre_echeances": 2, "annee_debut": 2026, "mois_debut": 3}).json()
    assert client.post(f"/prets/{p['id']}/annuler", headers=admin).json()["statut"] == "annule"
    assert client.post(f"/prets/{p['id']}/annuler", headers=admin).status_code == 409


# ---------------------------------------------------------------- solde de tout compte
def test_solde_licenciement_avec_tranches(client, db, admin):
    sid = nouveau(client, admin, embauche="2010-03-01")      # 16 ans 4 mois à fin juin 2026
    ap = client.get("/soldes/apercu", headers=admin, params={"salarie_id": sid, "date_sortie": "2026-06-30", "motif": "licenciement"}).json()
    # 250 000 × (5×30 % + 5×35 % + 6,33×40 %) = 250 000 × (1,5 + 1,75 + 2,5333) ≈ 1 445 833
    assert abs(float(ap["indemnite_licenciement"]) - 250000 * (1.5 + 1.75 + (195 / 12 - 10) * 0.4)) < 1
    assert float(ap["licenciement_non_imposable"]) == 50000                      # plafond PLAF_LIC
    assert float(ap["licenciement_imposable"]) == float(ap["indemnite_licenciement"]) - 50000
    r = client.post("/soldes", headers=admin, json={"salarie_id": sid, "date_sortie": "2026-06-30", "motif": "licenciement", "jours_conges": 10})
    assert r.status_code == 201, r.text
    cid = r.json()["campagne_id"]
    codes = {s["code"] for s in client.get(f"/campagnes/{cid}/saisies", headers=admin).json()}
    assert {"ICP", "LCI", "LCN"} <= codes
    icp = next(s for s in client.get(f"/campagnes/{cid}/saisies", headers=admin).json() if s["code"] == "ICP")
    assert float(icp["montant"]) == round(250000 * 10 / 26, 2)
    assert client.post(f"/campagnes/{cid}/calculer", headers=admin).json()["calcules"] == 1
    fiche = client.get(f"/salaries/{sid}", headers=admin).json()
    assert fiche["est_actif"] is False and fiche["motif_sortie"] == "licenciement"
    # un seul solde par salarié
    assert client.post("/soldes", headers=admin, json={"salarie_id": sid, "date_sortie": "2026-06-30", "motif": "licenciement"}).status_code == 409


def test_solde_demission_sans_indemnite_de_licenciement(client, admin):
    sid = nouveau(client, admin, matricule="11")
    cid = client.post("/soldes", headers=admin, json={"salarie_id": sid, "date_sortie": "2026-06-15", "motif": "demission", "jours_conges": 5}).json()["campagne_id"]
    codes = {s["code"] for s in client.get(f"/campagnes/{cid}/saisies", headers=admin).json()}
    assert codes == {"ICP"}
    p = client.get(f"/campagnes/{cid}/presences", headers=admin).json()[0]
    assert float(p["jours_payes"]) == 15


def test_solde_solde_le_pret_restant(client, admin):
    sid = nouveau(client, admin, matricule="12")
    client.post("/prets", headers=admin, json={"salarie_id": sid, "libelle": "Prêt", "montant": 90000, "nombre_echeances": 9, "annee_debut": 2026, "mois_debut": 6})
    cid = client.post("/soldes", headers=admin, json={"salarie_id": sid, "date_sortie": "2026-06-30", "motif": "demission"}).json()["campagne_id"]
    client.post(f"/campagnes/{cid}/calculer", headers=admin)
    pre = [s for s in client.get(f"/campagnes/{cid}/saisies", headers=admin).json() if s["code"] == "PRE"]
    assert len(pre) == 1 and float(pre[0]["montant"]) == 90000                  # les 9 échéances restantes d'un coup


# ---------------------------------------------------------------- saisie groupée
def test_saisie_en_masse(client, admin):
    a, b = nouveau(client, admin, matricule="20"), nouveau(client, admin, matricule="21")
    cid = client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 12}).json()["id"]
    client.post(f"/campagnes/{cid}/initialiser", headers=admin)
    r = client.post(f"/campagnes/{cid}/saisies/en-masse", headers=admin, json={"code": "GRT", "mode": "pourcentage_salaire", "valeur": 10})
    assert r.json()["ajoutees"] == 2
    assert {float(s["montant"]) for s in client.get(f"/campagnes/{cid}/saisies", headers=admin).json()} == {25000.0}
    assert client.post(f"/campagnes/{cid}/saisies/en-masse", headers=admin, json={"code": "XXX", "mode": "fixe", "valeur": 5}).status_code == 422


def test_droits_conges(client, db):
    creer_compte(db, "simple", role="paie", permissions=["lancer_paie"])
    h = connexion(client, "simple")
    assert client.get("/conges", headers=h).status_code == 403
    assert client.get("/prets", headers=h).status_code == 403
