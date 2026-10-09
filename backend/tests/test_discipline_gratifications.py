from decimal import Decimal as D

import pytest

from tests.conftest import connexion, creer_compte
from tests.test_virements_declarations import campagne_validee, salarie  # noqa: F401  (fixture réutilisée)


@pytest.fixture
def admin(client, db):
    creer_compte(db)
    return connexion(client)


def mesure(client, h, sid, **plus):
    corps = {"salarie_id": sid, "type_mesure": "avertissement", "date_decision": "2026-03-10", "motif": "Retards répétés."}
    return client.post("/discipline/mesures", headers=h, json={**corps, **plus})


# ---------------------------------------------------------------- discipline
def test_mesure_creee_avec_reference_et_pdf(client, admin):
    sid = salarie(client, admin, "1")
    r = mesure(client, admin, sid)
    assert r.status_code == 201 and r.json()["reference"].startswith("DISC-2026-")
    pdf = client.get(f"/discipline/mesures/{r.json()['id']}/lettre.pdf", headers=admin)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_mise_a_pied_exige_les_dates(client, admin):
    sid = salarie(client, admin, "1")
    assert mesure(client, admin, sid, type_mesure="mise_a_pied").status_code == 422
    r = mesure(client, admin, sid, type_mesure="mise_a_pied", debut_mise_a_pied="2026-03-09", fin_mise_a_pied="2026-03-02")
    assert r.status_code == 422


def test_mise_a_pied_retire_les_jours_ouvres_de_la_paie(client, admin):
    sid = salarie(client, admin, "1")
    cid = client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 3}).json()["id"]
    client.post(f"/campagnes/{cid}/initialiser", headers=admin)
    client.post(f"/campagnes/{cid}/calculer", headers=admin)
    avant = D(str(client.get(f"/campagnes/{cid}/bulletins", headers=admin).json()[0]["net_a_payer"]))
    # lundi 9 → mercredi 11 mars 2026 inclus (3 jours ouvrés) + week-end 14-15 (non compté)
    m = mesure(client, admin, sid, type_mesure="mise_a_pied", debut_mise_a_pied="2026-03-09", fin_mise_a_pied="2026-03-15").json()
    assert m["jours_non_payes"] == 5
    client.post(f"/campagnes/{cid}/calculer", headers=admin)
    b = client.get(f"/campagnes/{cid}/bulletins", headers=admin).json()[0]
    lignes = client.get(f"/bulletins/{b['id']}", headers=admin).json()["lignes"]
    ja = next(l for l in lignes if l["code"] == "JA")
    assert D(str(ja["base"] if "base" in ja else ja.get("quantite"))) == 5
    assert D(str(b["net_a_payer"])) < avant
    pres = client.get(f"/campagnes/{cid}/presences", headers=admin).json()[0]
    assert pres["jours_mise_a_pied"] == 5


def test_mesure_annulee_ne_pese_plus_sur_la_paie(client, admin):
    sid = salarie(client, admin, "1")
    m = mesure(client, admin, sid, type_mesure="mise_a_pied", debut_mise_a_pied="2026-03-09", fin_mise_a_pied="2026-03-10").json()
    r = client.post(f"/discipline/mesures/{m['id']}/annuler", headers=admin, json={"motif": "Saisie erronée"})
    assert r.status_code == 200 and r.json()["statut"] == "annulee" and r.json()["jours_non_payes"] == 0
    assert client.post(f"/discipline/mesures/{m['id']}/annuler", headers=admin, json={"motif": "encore"}).status_code == 409
    cid = client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 3}).json()["id"]
    client.post(f"/campagnes/{cid}/initialiser", headers=admin)
    assert client.get(f"/campagnes/{cid}/presences", headers=admin).json()[0]["jours_mise_a_pied"] == 0


def test_notes_de_service(client, admin):
    r = client.post("/discipline/notes", headers=admin, json={"objet": "Horaires d'été", "contenu": "Les horaires changent.", "date_effet": "2026-06-01"})
    assert r.status_code == 201 and r.json()["reference"].startswith("NS-2026-")
    assert client.get(f"/discipline/notes/{r.json()['id']}/pdf", headers=admin).content[:4] == b"%PDF"
    assert client.post(f"/discipline/notes/{r.json()['id']}/annuler", headers=admin).json()["statut"] == "annulee"
    assert client.post("/discipline/notes", headers=admin, json={"objet": "x" * 5, "contenu": "abcdef", "date_effet": "2026-06-01", "service_id": 999999}).status_code == 422


def test_discipline_reservee_et_auditee(client, db, admin):
    creer_compte(db, identifiant="lecteur", role="direction")
    h = connexion(client, "lecteur")
    assert client.get("/discipline/mesures", headers=h).status_code == 403
    sid = salarie(client, admin, "1")
    mesure(client, admin, sid)
    actions = [a["action"] for a in client.get("/admin/audit?taille=50", headers=admin).json()["elements"]]
    assert "mesure_disciplinaire_creee" in actions


# ---------------------------------------------------------------- gratifications
def test_gratifications_proposer_enregistrer_et_calculer(client, admin):
    s1, s2 = salarie(client, admin, "1"), salarie(client, admin, "2")
    cid = client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 3}).json()["id"]
    client.post(f"/campagnes/{cid}/initialiser", headers=admin)
    prop = client.post(f"/campagnes/{cid}/gratifications/proposer", headers=admin, json={"mode": "pourcentage_salaire", "valeur": 10}).json()
    assert D(str(prop["montants"][str(s1)])) == D("32000.00")           # 10 % de 300 000 + 20 000
    r = client.put(f"/campagnes/{cid}/gratifications", headers=admin, json={"lignes": [
        {"salarie_id": s1, "montant": 32000}, {"salarie_id": s2, "montant": None}]})
    assert r.status_code == 200 and r.json()["enregistrees"] == 1
    lst = client.get(f"/campagnes/{cid}/gratifications", headers=admin).json()["salaries"]
    assert {l["matricule"]: l["montant"] for l in lst}["000001"] is not None
    # ré-enregistrer remplace, sans doublon
    client.put(f"/campagnes/{cid}/gratifications", headers=admin, json={"lignes": [{"salarie_id": s1, "montant": 50000}]})
    saisies = [x for x in client.get(f"/campagnes/{cid}/saisies", headers=admin).json() if x["code"] == "GRT"]
    assert len(saisies) == 1 and D(str(saisies[0]["montant"])) == 50000
    assert client.post(f"/campagnes/{cid}/calculer", headers=admin).json()["calcules"] == 2
    # montant vide = suppression
    client.put(f"/campagnes/{cid}/gratifications", headers=admin, json={"lignes": [{"salarie_id": s1, "montant": 0}]})
    assert not [x for x in client.get(f"/campagnes/{cid}/saisies", headers=admin).json() if x["code"] == "GRT"]


def test_gratifications_refusees_si_campagne_validee_ou_salarie_hors_campagne(client, admin, campagne_validee):
    assert client.put(f"/campagnes/{campagne_validee}/gratifications", headers=admin, json={"lignes": []}).status_code == 409


def test_gratifications_salarie_hors_campagne(client, admin):
    s1 = salarie(client, admin, "1")
    cid = client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 3}).json()["id"]
    assert client.put(f"/campagnes/{cid}/gratifications", headers=admin, json={"lignes": [{"salarie_id": s1, "montant": 10}]}).status_code == 422


# ---------------------------------------------------------------- lettres de virement
def test_lettres_de_virement(client, admin, campagne_validee):
    lot = client.post(f"/campagnes/{campagne_validee}/virements", headers=admin, json={}).json()
    r = client.get(f"/virements/{lot['id']}/lettres.pdf", headers=admin)
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    audits = [a for a in client.get("/admin/audit?taille=50", headers=admin).json()["elements"] if a["action"] == "virement_lettres_exportees"]
    assert audits and audits[0]["detail"]["rib_en_clair"] is True
    client.post(f"/virements/{lot['id']}/annuler", headers=admin)
    assert client.get(f"/virements/{lot['id']}/lettres.pdf", headers=admin).status_code == 409
