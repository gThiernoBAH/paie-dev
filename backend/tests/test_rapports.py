from decimal import Decimal as D

import pytest
from sqlalchemy import text

from tests.conftest import connexion, creer_compte


@pytest.fixture
def admin(client, db):
    creer_compte(db)
    return connexion(client)


@pytest.fixture
def paie_validee(client, db, admin):
    for ref in (("service", "EXP", "Exploitation"), ("service", "ADM", "Administration")):
        client.post("/referentiels", headers=admin, json={"type_ref": ref[0], "code": ref[1], "libelle": ref[2]})
    services = {r["code"]: r["id"] for r in client.get("/referentiels?type_ref=service", headers=admin).json()}
    for mat, serv, base in (("1", "EXP", 200000), ("2", "EXP", 300000), ("3", "ADM", 400000)):
        r = client.post("/salaries", headers=admin, json={"nom": f"N{mat}", "matricule": mat, "date_embauche": "2021-01-01",
                                                          "salaire_base": base, "service_id": services[serv], "sexe": "M"})
        assert r.status_code == 201, r.text
    cid = client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 3}).json()["id"]
    client.post(f"/campagnes/{cid}/initialiser", headers=admin)
    p = client.get(f"/campagnes/{cid}/presences", headers=admin).json()[0]
    client.put(f"/campagnes/{cid}/presences/{p['salarie_id']}", headers=admin, json={"hs1": 4})
    client.post(f"/campagnes/{cid}/calculer", headers=admin)
    db.execute(text("UPDATE valeurs_parametres SET statut = 'confirme'"))
    db.commit()
    assert client.post(f"/campagnes/{cid}/valider", headers=admin).status_code == 200
    return cid


def test_masse_salariale_somme_les_bulletins(client, admin, paie_validee):
    r = client.get("/rapports/masse-salariale?annee=2026", headers=admin).json()
    assert len(r["lignes"]) == 1 and r["lignes"][0][0] == "Mars" and r["lignes"][0][1] == 3
    bulletins = client.get(f"/campagnes/{paie_validee}/bulletins", headers=admin).json()
    assert D(r["totaux"]["Net payé"]) == sum(D(str(b["net_a_payer"])) for b in bulletins)
    assert D(r["totaux"]["Coût employeur"]) > D(r["totaux"]["Salaire brut imposable"])


def test_par_service(client, admin, paie_validee):
    r = client.get("/rapports/par-service?annee=2026&mois=3", headers=admin).json()
    par = {l[0]: l[1] for l in r["lignes"]}
    assert par == {"Exploitation": 2, "Administration": 1}


def test_heures_supplementaires(client, admin, paie_validee):
    r = client.get("/rapports/heures-supplementaires?annee=2026", headers=admin).json()
    assert r["lignes"][0][1] == 1 and D(r["lignes"][0][2]) == 4 and D(r["totaux"]["Montant des HS"]) > 0


def test_effectif_et_mouvements(client, admin, paie_validee):
    e = client.get("/rapports/effectif", headers=admin).json()
    assert ["Total", "Effectif", 3] in e["lignes"] and ["Service", "Exploitation", 2] in e["lignes"]
    m = client.get("/rapports/mouvements?du=2021-01-01&au=2021-12-31", headers=admin).json()
    assert len(m["lignes"]) == 3 and all(l[1] == "Entrée" for l in m["lignes"])
    assert client.get("/rapports/mouvements?du=2022-01-01&au=2021-01-01", headers=admin).status_code == 422


def test_exports_fichier(client, admin, paie_validee):
    assert client.get("/rapports/masse-salariale?annee=2026&format=xlsx", headers=admin).content[:2] == b"PK"
    assert client.get("/rapports/par-service?annee=2026&mois=3&format=csv", headers=admin).content.startswith(b"\xef\xbb\xbf")


def test_livre_de_paie_reserve_aux_droits_sensibles_et_trace(client, db, admin, paie_validee):
    r = client.get("/rapports/livre-de-paie?annee=2026&mois=3", headers=admin).json()
    assert len(r["lignes"]) == 3
    creer_compte(db, "dir", role="direction", permissions=["voir_rapports"])
    h = connexion(client, "dir")
    assert client.get("/rapports/livre-de-paie?annee=2026&mois=3", headers=h).status_code == 403
    assert client.get("/rapports/masse-salariale?annee=2026", headers=h).status_code == 200      # agrégats : autorisés
    actions = [a["action"] for a in client.get("/admin/audit?taille=100", headers=admin).json()["elements"]]
    assert "livre_de_paie_consulte" in actions


def test_tableau_de_bord_selon_les_droits(client, db, admin, paie_validee):
    t = client.get("/tableau-de-bord", headers=admin).json()
    assert t["effectif_actif"] == 3 and t["derniere_paie"]["bulletins"] == 3
    assert t["a_traiter"]["parametres_critiques_a_confirmer"] == 0 and t["a_traiter"]["conges_en_attente"] == 0
    creer_compte(db, "compta", role="direction", permissions=["voir_declarations"])
    h = connexion(client, "compta")
    t2 = client.get("/tableau-de-bord", headers=h).json()
    assert t2["effectif_actif"] is None and t2["derniere_paie"] is None and t2["a_traiter"] == {}
    creer_compte(db, "sal", role="salarie")
    assert client.get("/tableau-de-bord", headers=connexion(client, "sal")).status_code == 403


def test_rapports_refuses_sans_droit(client, db):
    creer_compte(db, "x", role="paie", permissions=["lancer_paie"])
    h = connexion(client, "x")
    for c in ("/rapports/masse-salariale?annee=2026", "/rapports/effectif", "/rapports/heures-supplementaires?annee=2026"):
        assert client.get(c, headers=h).status_code == 403, c
