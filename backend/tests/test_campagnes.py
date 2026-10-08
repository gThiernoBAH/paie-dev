from datetime import date

import pytest
from sqlalchemy import text

from app.core import models
from tests.conftest import connexion, creer_compte


@pytest.fixture
def admin(client, db):
    creer_compte(db)
    return connexion(client)


def tout_confirmer(db):
    db.execute(text("UPDATE valeurs_parametres SET statut = 'confirme'"))
    db.commit()


def salarie_gt10(client, h):
    r = client.post("/salaries", headers=h, json={
        "nom": "TEST", "prenoms": "Gt", "matricule": "54", "nombre_parts": 5, "nombre_enfants": 8, "nombre_personnes_cmu": 4,
        "indemnite_transport": 38102, "date_embauche": "1988-01-04", "salaire_base": 135540, "sursalaire": 69899,
        "numero_cnps": "1234567890"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def preparer_gt10(client, db, h):
    for code, lib, typ in (("PLA", "Prime", "GN"), ("PLT", "Prime", "GN"), ("C08", "Retenue", "RN")):
        db.add(models.Rubrique(code=code, libelle=lib, type=typ))
    db.commit()
    sid = salarie_gt10(client, h)
    camp = client.post("/campagnes", headers=h, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 1}).json()
    cid = camp["id"]
    assert client.post(f"/campagnes/{cid}/initialiser", headers=h).json()["ajoutes"] == 1
    r = client.put(f"/campagnes/{cid}/presences/{sid}", headers=h, json={"jours_absence_ja": 3, "heures_absence": 4, "hs1": 3})
    assert r.status_code == 200, r.text
    for code, m in (("SAL", "5625.18"), ("PLA", 3029), ("PLT", 1500), ("AS1", 8600), ("C08", 25000)):
        assert client.post(f"/campagnes/{cid}/saisies", headers=h, json={"salarie_id": sid, "code": code, "montant": m}).status_code == 201
    return cid, sid


def test_gt10_de_bout_en_bout(client, db, admin):
    cid, sid = preparer_gt10(client, db, admin)
    r = client.post(f"/campagnes/{cid}/calculer", headers=admin)
    assert r.status_code == 200 and r.json()["calcules"] == 1 and not r.json()["erreurs"]
    b = client.get(f"/campagnes/{cid}/bulletins", headers=admin).json()[0]
    assert float(b["net_a_payer"]) == 205014 and float(b["cnps"]) == 14058 and float(b["its"]) == 0
    detail = client.get(f"/bulletins/{b['id']}", headers=admin).json()
    assert detail["statut"] == "brouillon" and any(l["code"] == "HS1" for l in detail["lignes"])


def test_validation_bloquee_tant_que_parametres_critiques_a_confirmer(client, db, admin):
    cid, _ = preparer_gt10(client, db, admin)
    client.post(f"/campagnes/{cid}/calculer", headers=admin)
    r = client.post(f"/campagnes/{cid}/valider", headers=admin)
    assert r.status_code == 409 and "critiques à confirmer" in r.json()["detail"]
    tout_confirmer(db)
    r = client.post(f"/campagnes/{cid}/valider", headers=admin)
    assert r.status_code == 200 and r.json()["bulletins_valides"] == 1


def test_campagne_validee_est_figee(client, db, admin):
    cid, sid = preparer_gt10(client, db, admin)
    client.post(f"/campagnes/{cid}/calculer", headers=admin)
    tout_confirmer(db)
    assert client.post(f"/campagnes/{cid}/valider", headers=admin).status_code == 200
    assert client.post(f"/campagnes/{cid}/calculer", headers=admin).status_code == 409
    assert client.put(f"/campagnes/{cid}/presences/{sid}", headers=admin, json={"hs1": 1}).status_code == 409
    assert client.post(f"/campagnes/{cid}/saisies", headers=admin, json={"salarie_id": sid, "code": "SAL", "montant": 1}).status_code == 409
    assert client.delete(f"/campagnes/{cid}", headers=admin).status_code == 409


def test_trigger_bloque_la_modification_sql_d_un_bulletin_valide(client, db, admin):
    cid, _ = preparer_gt10(client, db, admin)
    client.post(f"/campagnes/{cid}/calculer", headers=admin)
    tout_confirmer(db)
    client.post(f"/campagnes/{cid}/valider", headers=admin)
    with pytest.raises(Exception):
        db.execute(text("UPDATE bulletins SET net_a_payer = 1"))
        db.commit()
    db.rollback()
    with pytest.raises(Exception):
        db.execute(text("DELETE FROM bulletins"))
        db.commit()
    db.rollback()


def test_rouvrir_reserve_a_l_admin_avec_motif(client, db, admin):
    cid, _ = preparer_gt10(client, db, admin)
    client.post(f"/campagnes/{cid}/calculer", headers=admin)
    tout_confirmer(db)
    client.post(f"/campagnes/{cid}/valider", headers=admin)
    assert client.post(f"/campagnes/{cid}/rouvrir", headers=admin, json={"motif": "x"}).status_code == 422
    r = client.post(f"/campagnes/{cid}/rouvrir", headers=admin, json={"motif": "Erreur de saisie d'une prime"})
    assert r.status_code == 200 and r.json()["statut"] == "calculee"
    assert client.get(f"/campagnes/{cid}/bulletins", headers=admin).json()[0]["statut"] == "brouillon"
    creer_compte(db, "gest", role="paie", permissions=["lancer_paie", "valider_bulletins"])
    g = connexion(client, "gest")
    tout_confirmer(db)
    assert client.post(f"/campagnes/{cid}/valider", headers=g).status_code == 200
    assert client.post(f"/campagnes/{cid}/rouvrir", headers=g, json={"motif": "Tentative non autorisée"}).status_code == 403


def test_une_campagne_mensuelle_par_mois(client, admin):
    assert client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 2}).status_code == 201
    assert client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 2}).status_code == 409


def test_campagne_journaliere_et_numerotation(client, db, admin):
    h = admin
    s = client.post("/salaries", headers=h, json={"nom": "JOUR", "matricule": "7", "type_remuneration": "journalier",
                                                  "salaire_base": 75000, "date_embauche": "2020-01-01"}).json()["id"]
    for jour in ("2026-01-02", "2026-01-03", "2026-01-04"):
        client.put("/pointages", headers=h, json={"salarie_id": s, "jour": jour, "heure_entree": "08:00", "heure_sortie": "16:00"})
    c1 = client.post("/campagnes", headers=h, json={"type_campagne": "journaliere", "annee": 2026, "mois": 1,
                                                    "debut": "2026-01-01", "fin": "2026-01-15"}).json()
    c2 = client.post("/campagnes", headers=h, json={"type_campagne": "journaliere", "annee": 2026, "mois": 1,
                                                    "debut": "2026-01-16", "fin": "2026-01-31"}).json()
    assert (c1["numero"], c2["numero"]) == (1, 2)
    assert client.post(f"/campagnes/{c1['id']}/initialiser", headers=h).json()["ajoutes"] == 1
    assert client.post(f"/campagnes/{c2['id']}/initialiser", headers=h).json()["ajoutes"] == 0   # aucun pointage sur la 2e quinzaine
    r = client.post(f"/campagnes/{c1['id']}/presences/depuis-pointages", headers=h, json={}).json()
    assert r["mises_a_jour"] == 1
    p = client.get(f"/campagnes/{c1['id']}/presences", headers=h).json()[0]
    assert float(p["jours_presence"]) == 3 and p["source"] == "pointage"
    rr = client.post(f"/campagnes/{c1['id']}/calculer", headers=h).json()
    assert rr["calcules"] == 1, rr


def test_salarie_sans_salaire_signale_sans_bloquer_les_autres(client, db, admin):
    cid, _ = preparer_gt10(client, db, admin)
    autre = client.post("/salaries", headers=admin, json={"nom": "SANS", "matricule": "99"}).json()["id"]
    client.post(f"/campagnes/{cid}/salaries", headers=admin, json={"salarie_id": autre})
    r = client.post(f"/campagnes/{cid}/calculer", headers=admin).json()
    assert r["calcules"] == 1 and r["erreurs"][0]["matricule"] == "000099"


def test_pdf_bulletin_et_audit(client, db, admin):
    cid, _ = preparer_gt10(client, db, admin)
    client.post(f"/campagnes/{cid}/calculer", headers=admin)
    bid = client.get(f"/campagnes/{cid}/bulletins", headers=admin).json()[0]["id"]
    r = client.get(f"/bulletins/{bid}/pdf", headers=admin)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    from pypdf import PdfReader
    from io import BytesIO
    texte = PdfReader(BytesIO(r.content)).pages[0].extract_text()
    assert "205 014" in texte and "1234567890" in texte and "deux cent cinq mille quatorze" in texte.lower()
    assert client.get(f"/campagnes/{cid}/bulletins.pdf", headers=admin).content.startswith(b"%PDF")
    actions = [a["action"] for a in client.get("/admin/audit?taille=200", headers=admin).json()["elements"]]
    assert "bulletin_imprime" in actions and "campagne_calculee" in actions


def test_droits(client, db, admin):
    creer_compte(db, "lecteur", role="paie", permissions=["voir_rapports"])
    h = connexion(client, "lecteur")
    assert client.get("/campagnes", headers=h).status_code == 200
    assert client.post("/campagnes", headers=h, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 3}).status_code == 403
    creer_compte(db, "rien", role="salarie")
    assert client.get("/campagnes", headers=connexion(client, "rien")).status_code == 403
