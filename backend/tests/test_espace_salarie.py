from datetime import date, timedelta

import pytest
from sqlalchemy import text

from tests.conftest import connexion, creer_compte


@pytest.fixture
def admin(client, db):
    creer_compte(db)
    return connexion(client)


def salarie(client, h, matricule):
    r = client.post("/salaries", headers=h, json={"nom": f"NOM{matricule}", "prenoms": "Awa", "matricule": matricule,
                                                  "date_embauche": "2022-01-01", "salaire_base": 250000})
    sid = r.json()["id"]
    c = client.post(f"/salaries/{sid}/creer-compte", headers=h).json()
    return sid, c["utilisateur"]["identifiant"], c["mot_de_passe_temporaire"]


def session_salarie(client, identifiant, mdp):
    r = client.post("/auth/login", json={"identifiant": identifiant, "password": mdp})
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.post("/auth/mot-de-passe", headers=h, json={"ancien_mot_de_passe": mdp, "nouveau_mot_de_passe": "NouveauMotDePasse2026"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def deux_salaries(client, db, admin):
    a = salarie(client, admin, "1")
    b = salarie(client, admin, "2")
    cid = client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 3}).json()["id"]
    client.post(f"/campagnes/{cid}/initialiser", headers=admin)
    client.post(f"/campagnes/{cid}/calculer", headers=admin)
    return cid, a, b


def valider(client, db, admin, cid):
    db.execute(text("UPDATE valeurs_parametres SET statut = 'confirme'"))
    db.commit()
    assert client.post(f"/campagnes/{cid}/valider", headers=admin).status_code == 200


def test_le_salarie_ne_voit_que_ses_bulletins_valides(client, db, admin, deux_salaries):
    cid, a, b = deux_salaries
    h = session_salarie(client, a[1], a[2])
    assert client.get("/moi/bulletins", headers=h).json() == []                    # brouillon : invisible
    valider(client, db, admin, cid)
    mes = client.get("/moi/bulletins", headers=h).json()
    assert len(mes) == 1 and mes[0]["lu"] is False
    detail = client.get(f"/moi/bulletins/{mes[0]['id']}", headers=h).json()
    assert float(detail["net_a_payer"]) > 0 and detail["lignes"]
    pdf = client.get(f"/moi/bulletins/{mes[0]['id']}/pdf", headers=h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get("/moi/bulletins", headers=h).json()[0]["lu"] is True


def test_acces_au_bulletin_d_un_autre_salarie_impossible(client, db, admin, deux_salaries):
    cid, a, b = deux_salaries
    valider(client, db, admin, cid)
    ha, hb = session_salarie(client, a[1], a[2]), session_salarie(client, b[1], b[2])
    id_b = client.get("/moi/bulletins", headers=hb).json()[0]["id"]
    assert client.get(f"/moi/bulletins/{id_b}", headers=ha).status_code == 404
    assert client.get(f"/moi/bulletins/{id_b}/pdf", headers=ha).status_code == 404
    assert client.get(f"/moi/bulletins/9999", headers=ha).status_code == 404


def test_le_salarie_n_accede_pas_aux_routes_de_gestion(client, db, admin, deux_salaries):
    cid, a, _ = deux_salaries
    h = session_salarie(client, a[1], a[2])
    for chemin in ("/campagnes", "/salaries", "/virements", "/conges", "/prets", "/admin/utilisateurs", "/declarations/its?annee=2026&mois=3"):
        assert client.get(chemin, headers=h).status_code == 403, chemin
    assert client.get(f"/campagnes/{cid}/bulletins.pdf", headers=h).status_code == 403


def test_les_routes_moi_sont_fermees_aux_non_salaries(client, admin):
    for chemin in ("/moi/profil", "/moi/bulletins", "/moi/conges", "/moi/prets"):
        assert client.get(chemin, headers=admin).status_code == 403, chemin


def test_demande_de_conge_par_le_salarie(client, db, admin, deux_salaries):
    _, a, _ = deux_salaries
    h = session_salarie(client, a[1], a[2])
    demain = date.today() + timedelta(days=30)
    lundi = demain - timedelta(days=demain.weekday())
    corps = {"debut": lundi.isoformat(), "fin": (lundi + timedelta(days=5)).isoformat()}
    r = client.post("/moi/conges", headers=h, json=corps)
    assert r.status_code == 201 and r.json()["statut"] == "demande"
    assert client.post("/moi/conges", headers=h, json=corps).status_code == 409                 # chevauchement
    assert client.post("/moi/conges", headers=h, json={"debut": "2020-01-01", "fin": "2020-01-05"}).status_code == 422   # passé
    vue = client.get("/moi/conges", headers=h).json()
    assert len(vue["demandes"]) == 1 and float(vue["solde"]["solde"]) > 0
    # visible côté gestionnaire, qui décide
    assert client.get("/conges?statut=demande", headers=admin).json()[0]["matricule"] == "000001"
    assert client.delete(f"/moi/conges/{r.json()['id']}", headers=h).status_code == 204


def test_on_ne_retire_pas_la_demande_d_un_autre(client, db, admin, deux_salaries):
    _, a, b = deux_salaries
    ha, hb = session_salarie(client, a[1], a[2]), session_salarie(client, b[1], b[2])
    lundi = date.today() + timedelta(days=60)
    lundi -= timedelta(days=lundi.weekday())
    cid = client.post("/moi/conges", headers=hb, json={"debut": lundi.isoformat(), "fin": lundi.isoformat()}).json()["id"]
    assert client.delete(f"/moi/conges/{cid}", headers=ha).status_code == 404


def test_profil_sans_donnees_sensibles(client, admin, deux_salaries):
    _, a, _ = deux_salaries
    h = session_salarie(client, a[1], a[2])
    p = client.get("/moi/profil", headers=h).json()
    assert p["matricule"] == "000001" and "rib" not in str(p).lower().replace("a_un_rib", "") and "salaire" not in p
