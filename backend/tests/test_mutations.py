"""Historique des mutations : affectation (service, section…) et salaire, fusionnés dans une frise."""
import pytest

from app.core.permissions import PERMISSIONS_PAR_DEFAUT
from tests.conftest import connexion, creer_compte


@pytest.fixture
def admin(client, db):
    creer_compte(db)
    return connexion(client)


def _ref(client, h, type_ref, code, libelle):
    r = client.post("/referentiels", headers=h, json={"type_ref": type_ref, "code": code, "libelle": libelle})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_un_changement_de_service_est_historise(client, admin):
    compta = _ref(client, admin, "service", "CPT", "Comptabilité")
    prod = _ref(client, admin, "service", "PRD", "Production")
    sal = client.post("/salaries", headers=admin, json={"nom": "KONE", "date_embauche": "2022-01-03", "service_id": compta,
                                                         "salaire_base": 200000}).json()
    r = client.patch(f"/salaries/{sal['id']}", headers=admin,
                     json={"service_id": prod, "date_effet_mutation": "2026-09-01", "motif_mutation": "Réorganisation"})
    assert r.status_code == 200 and r.json()["service"]["libelle"] == "Production"
    h = client.get(f"/salaries/{sal['id']}/historique", headers=admin).json()
    mut = [l for l in h if l["nature"] == "service"]
    assert len(mut) == 1
    assert mut[0]["avant"] == "Comptabilité" and mut[0]["apres"] == "Production"
    assert mut[0]["date"] == "2026-09-01" and mut[0]["motif"] == "Réorganisation" and mut[0]["par"] == "admin"
    # l'embauche et le salaire d'embauche figurent aussi, la frise est triée du plus récent au plus ancien
    assert [l["nature"] for l in h] == ["service", "salaire", "embauche"] or [l["nature"] for l in h][-1] == "embauche"
    dates = [l["date"] for l in h]
    assert dates == sorted(dates, reverse=True)


def test_modification_sans_changement_d_affectation_n_ajoute_rien(client, admin):
    sid = client.post("/salaries", headers=admin, json={"nom": "TRAORE"}).json()["id"]
    client.patch(f"/salaries/{sid}", headers=admin, json={"telephone": "0102030405"})
    assert [l for l in client.get(f"/salaries/{sid}/historique", headers=admin).json() if l["nature"] != "embauche"] == []


def test_plusieurs_champs_et_valeur_vide(client, admin):
    sec = _ref(client, admin, "section", "S1", "Atelier 1")
    cat = _ref(client, admin, "categorie", "C3", "Catégorie 3")
    sid = client.post("/salaries", headers=admin, json={"nom": "YAO"}).json()["id"]
    client.patch(f"/salaries/{sid}", headers=admin, json={"section_id": sec, "categorie_id": cat, "type_remuneration": "journalier"})
    natures = {l["nature"]: l for l in client.get(f"/salaries/{sid}/historique", headers=admin).json()}
    assert natures["section"]["avant"] is None and natures["section"]["apres"] == "Atelier 1"
    assert natures["categorie"]["apres"] == "Catégorie 3"
    assert natures["type_remuneration"]["avant"] == "Mensuel" and natures["type_remuneration"]["apres"] == "Journalier"
    # remise à vide
    client.patch(f"/salaries/{sid}", headers=admin, json={"section_id": None})
    h = client.get(f"/salaries/{sid}/historique", headers=admin).json()
    assert any(l["nature"] == "section" and l["avant"] == "Atelier 1" and l["apres"] is None for l in h)


def test_historique_du_salaire_et_du_depart(client, admin):
    sid = client.post("/salaries", headers=admin, json={"nom": "DIOP", "date_embauche": "2020-01-01", "salaire_base": 150000}).json()["id"]
    client.post(f"/salaries/{sid}/salaires", headers=admin, json={"date_effet": "2024-01-01", "montant": 180000, "sursalaire": 10000, "motif": "Promotion"})
    client.post(f"/salaries/{sid}/sortie", headers=admin, json={"date_sortie": "2026-06-30", "motif_sortie": "démission"})
    h = client.get(f"/salaries/{sid}/historique", headers=admin).json()
    assert [l["nature"] for l in h] == ["sortie", "salaire", "salaire", "embauche"]
    promo = h[1]
    assert promo["avant"] == "150 000 F" and promo["apres"] == "180 000 F + 10 000 F de sursalaire" and promo["motif"] == "Promotion"


def test_salaire_masque_sans_droit_sensible(client, db, admin):
    sid = client.post("/salaries", headers=admin, json={"nom": "SANGARE", "date_embauche": "2021-01-01", "salaire_base": 150000}).json()["id"]
    creer_compte(db, "gp", role="paie", permissions=PERMISSIONS_PAR_DEFAUT["paie"])
    h = connexion(client, "gp")
    nat = [l["nature"] for l in client.get(f"/salaries/{sid}/historique", headers=h).json()]
    assert "salaire" not in nat and "embauche" in nat
    creer_compte(db, "nu", role="salarie")
    assert client.get(f"/salaries/{sid}/historique", headers=connexion(client, "nu")).status_code == 403
