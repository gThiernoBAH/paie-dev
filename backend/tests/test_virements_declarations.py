from decimal import Decimal as D
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import text

from tests.conftest import connexion, creer_compte


@pytest.fixture
def admin(client, db):
    creer_compte(db)
    return connexion(client)


def salarie(client, h, matricule, **plus):
    base = {"nom": f"NOM{matricule}", "prenoms": "Test", "matricule": matricule, "date_embauche": "2020-01-01",
            "salaire_base": 300000, "sursalaire": 20000, "mode_paiement": "virement", "numero_cnps": f"99{matricule}00"}
    r = client.post("/salaries", headers=h, json={**base, **plus})
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.fixture
def campagne_validee(client, db, admin):
    salarie(client, admin, "1", rib="CI0080101234567890123456")
    salarie(client, admin, "2")                                      # pas de RIB
    salarie(client, admin, "3", mode_paiement="especes")
    cid = client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 3}).json()["id"]
    client.post(f"/campagnes/{cid}/initialiser", headers=admin)
    assert client.post(f"/campagnes/{cid}/calculer", headers=admin).json()["calcules"] == 3
    db.execute(text("UPDATE valeurs_parametres SET statut = 'confirme'"))
    db.commit()
    assert client.post(f"/campagnes/{cid}/valider", headers=admin).status_code == 200
    return cid


# ---------------------------------------------------------------- virements
def test_lot_exclut_sans_rib_et_especes(client, admin, campagne_validee):
    r = client.post(f"/campagnes/{campagne_validee}/virements", headers=admin, json={})
    assert r.status_code == 201, r.text
    lot = r.json()
    assert lot["nombre_ordres"] == 1 and len(lot["exclus"]) == 2
    assert {e["motif"].split(" ")[0] for e in lot["exclus"]} == {"RIB", "Paiement"}
    net = client.get(f"/campagnes/{campagne_validee}/bulletins", headers=admin).json()[0]["net_a_payer"]
    assert float(lot["total"]) == float(net)
    assert client.post(f"/campagnes/{campagne_validee}/virements", headers=admin, json={}).status_code == 409   # un seul lot actif


def test_fichier_virement_avec_rib_en_clair_et_audit(client, admin, campagne_validee):
    lot = client.post(f"/campagnes/{campagne_validee}/virements", headers=admin, json={}).json()
    x = client.get(f"/virements/{lot['id']}/fichier?format=xlsx", headers=admin)
    ws = load_workbook(BytesIO(x.content)).active
    valeurs = [[c.value for c in row] for row in ws.iter_rows()]
    assert any("CI0080101234567890123456" in str(v) for row in valeurs for v in row)
    c = client.get(f"/virements/{lot['id']}/fichier?format=csv", headers=admin)
    assert c.content.startswith(b"\xef\xbb\xbf") and b"CI0080101234567890123456" in c.content
    actions = [a["action"] for a in client.get("/admin/audit?taille=200", headers=admin).json()["elements"]]
    assert actions.count("virement_fichier_exporte") == 2
    # le détail du lot ne divulgue jamais le RIB
    assert "CI0080101234567890123456" not in client.get(f"/virements/{lot['id']}", headers=admin).text


def test_lancer_et_annuler(client, admin, campagne_validee):
    lot = client.post(f"/campagnes/{campagne_validee}/virements", headers=admin, json={}).json()
    assert client.post(f"/virements/{lot['id']}/lancer", headers=admin).json()["statut"] == "lance"
    assert client.post(f"/virements/{lot['id']}/lancer", headers=admin).status_code == 409
    assert client.post(f"/virements/{lot['id']}/annuler", headers=admin).status_code == 409
    lot2 = client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 4}).json()
    assert client.post(f"/campagnes/{lot2['id']}/virements", headers=admin, json={}).status_code == 409   # campagne non validée


def test_annulation_permet_un_nouveau_lot(client, admin, campagne_validee):
    lot = client.post(f"/campagnes/{campagne_validee}/virements", headers=admin, json={}).json()
    assert client.post(f"/virements/{lot['id']}/annuler", headers=admin).json()["statut"] == "annule"
    assert client.post(f"/campagnes/{campagne_validee}/virements", headers=admin, json={}).status_code == 201


# ---------------------------------------------------------------- déclarations
def test_etats_cnps_its_fdfp(client, admin, campagne_validee):
    cnps = client.get("/declarations/cnps?annee=2026&mois=3", headers=admin).json()
    assert len(cnps["lignes"]) == 3 and cnps["lignes"][0][1] == "9910" + "0" or cnps["lignes"][0][1].startswith("99")
    bulletins = client.get(f"/campagnes/{campagne_validee}/bulletins", headers=admin).json()
    assert D(cnps["totaux"]["Retraite salarié"]) == sum(D(str(b["cnps"])) for b in bulletins)
    its = client.get("/declarations/its?annee=2026&mois=3", headers=admin).json()
    assert D(its["totaux"]["ITS retenu"]) == sum(D(str(b["its"])) for b in bulletins)
    fdfp = client.get("/declarations/fdfp?annee=2026&mois=3", headers=admin).json()
    assert D(fdfp["totaux"]["Taxe d'apprentissage"]) > 0
    # un mois sans bulletin validé -> état vide
    assert client.get("/declarations/its?annee=2026&mois=4", headers=admin).json()["lignes"] == []


def test_disa_annuelle_et_exports(client, admin, campagne_validee):
    d = client.get("/declarations/disa?annee=2026", headers=admin).json()
    assert len(d["lignes"]) == 3 and d["lignes"][0][5] == 1
    x = client.get("/declarations/disa?annee=2026&format=xlsx", headers=admin)
    assert x.status_code == 200 and load_workbook(BytesIO(x.content)).active.max_row >= 5
    assert client.get("/declarations/its?annee=2026&format=csv", headers=admin).status_code == 422     # mois obligatoire
    assert client.get("/declarations/inconnu?annee=2026", headers=admin).status_code == 404


def test_cnps_et_disa_tracees_dans_l_audit(client, admin, campagne_validee):
    client.get("/declarations/cnps?annee=2026&mois=3", headers=admin)
    client.get("/declarations/its?annee=2026&mois=3", headers=admin)
    actions = [a["action"] for a in client.get("/admin/audit?taille=200", headers=admin).json()["elements"]]
    assert actions.count("declaration_consultee") == 1


# ---------------------------------------------------------------- journal comptable
def test_journal_equilibre(client, admin, campagne_validee):
    j = client.get(f"/campagnes/{campagne_validee}/journal-comptable", headers=admin).json()
    assert D(j["totaux"]["Débit"]) == D(j["totaux"]["Crédit"]) > 0
    comptes = {l[3] for l in j["lignes"]}
    assert {"661000", "664100", "431100", "422000"} <= comptes
    net = sum(D(str(b["net_a_payer"])) for b in client.get(f"/campagnes/{campagne_validee}/bulletins", headers=admin).json())
    assert sum(D(l[6]) for l in j["lignes"] if l[3] == "422000") == net
    assert client.get(f"/campagnes/{campagne_validee}/journal-comptable?format=csv", headers=admin).status_code == 200


def test_journal_respecte_les_comptes_parametres(client, admin, campagne_validee):
    r = client.post("/parametres/compta_compte_remunerations/valeurs", headers=admin, json={"valeur": "661100", "date_effet": "2026-01-01", "statut": "confirme", "source": "Comptable"})
    assert r.status_code in (200, 201), r.text
    comptes = {l[3] for l in client.get(f"/campagnes/{campagne_validee}/journal-comptable", headers=admin).json()["lignes"]}
    assert "661100" in comptes and "661000" not in comptes


def test_journal_refuse_campagne_non_validee(client, admin):
    cid = client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 5}).json()["id"]
    assert client.get(f"/campagnes/{cid}/journal-comptable", headers=admin).status_code == 409


def test_droits_lot7(client, db, admin, campagne_validee):
    creer_compte(db, "compta", role="direction", permissions=["voir_declarations"])
    h = connexion(client, "compta")
    assert client.get("/declarations/its?annee=2026&mois=3", headers=h).status_code == 200
    assert client.get("/virements", headers=h).status_code == 403
    assert client.post(f"/campagnes/{campagne_validee}/virements", headers=h, json={}).status_code == 403
