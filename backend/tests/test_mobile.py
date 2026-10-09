"""Canal mobile : lecture seule, administration interdite, exceptions limitées au salarié."""
from tests.conftest import connexion, creer_compte

MOBILE = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148"}


def _jeton_mobile(client, identifiant, mdp="MotDePasse2026"):
    r = client.post("/auth/login", json={"identifiant": identifiant, "password": mdp, "canal": "mobile"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_mobile_lecture_autorisee_ecriture_refusee(client, db):
    creer_compte(db, "admin", "admin")
    h = _jeton_mobile(client, "admin")
    assert client.get("/salaries", headers=h).status_code == 200            # lecture : oui
    r = client.post("/referentiels", headers=h, json={"type_ref": "service", "code": "XX", "libelle": "Test"})
    assert r.status_code == 403 and "Lecture seule" in r.json()["detail"]    # écriture : non, même pour l'admin
    assert client.patch("/referentiels/1", headers=h, json={"libelle": "x"}).status_code == 403
    assert client.delete("/pointages/1", headers=h).status_code == 403


def test_mobile_administration_interdite_meme_en_lecture(client, db):
    creer_compte(db, "admin", "admin")
    h = _jeton_mobile(client, "admin")
    r = client.get("/admin/utilisateurs", headers=h)
    assert r.status_code == 403 and "ordinateur" in r.json()["detail"]
    assert client.get("/admin/audit", headers=h).status_code == 403


def test_pc_inchange(client, db):
    creer_compte(db, "admin", "admin")
    h = connexion(client)
    assert client.get("/admin/utilisateurs", headers=h).status_code == 200
    assert client.post("/referentiels", headers=h, json={"type_ref": "service", "code": "XX", "libelle": "Test"}).status_code == 201


def test_telephone_detecte_par_user_agent_meme_sans_declaration(client, db):
    creer_compte(db, "admin", "admin")
    r = client.post("/auth/login", json={"identifiant": "admin", "password": "MotDePasse2026", "canal": "pc"}, headers=MOBILE)
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/admin/utilisateurs", headers=h).status_code == 403   # « pc » déclaré mais navigateur mobile


def test_salarie_mobile_garde_ses_demandes_de_conges_et_son_mot_de_passe(client, db):
    from app.core import models
    db.add(models.Salarie(matricule="000700", nom="DEMO", date_embauche=__import__("datetime").date(2020, 1, 1)))
    db.commit()
    creer_compte(db, "000700", "salarie")
    h = _jeton_mobile(client, "000700")
    r = client.post("/moi/conges", headers=h, json={"type_conge": "annuel", "debut": "2030-03-04", "fin": "2030-03-08"})
    assert r.status_code == 201, r.text
    assert client.delete(f"/moi/conges/{r.json()['id']}", headers=h).status_code == 204
    # Changer son mot de passe reste possible, et le nouveau jeton reste « mobile ».
    r = client.post("/auth/mot-de-passe", headers=h, json={"ancien_mot_de_passe": "MotDePasse2026", "nouveau_mot_de_passe": "NouveauMdp2026!x"})
    assert r.status_code == 200, r.text
    h2 = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.post("/referentiels", headers=h2, json={}).status_code == 403
