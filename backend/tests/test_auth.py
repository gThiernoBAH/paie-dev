import time

from app.core import crypto, tokens
from tests.conftest import connexion, creer_compte


def test_sante(client):
    assert client.get("/health").json() == {"statut": "ok"}


def test_connexion_ok_et_me(client, db):
    creer_compte(db, "admin", "admin")
    r = client.post("/auth/login", json={"identifiant": "admin", "password": "MotDePasse2026"})
    assert r.status_code == 200
    corps = r.json()
    assert corps["user"]["identifiant"] == "admin"
    assert "gerer_utilisateurs" in corps["user"]["permissions"]  # l'admin a tout
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {corps['access_token']}"})
    assert me.status_code == 200 and me.json()["role"] == "admin"


def test_matricule_avec_zeros_initiaux(client, db):
    creer_compte(db, "045700", "salarie")
    r = client.post("/auth/login", json={"identifiant": "045700", "password": "MotDePasse2026"})
    assert r.status_code == 200 and r.json()["user"]["identifiant"] == "045700"


def test_mauvais_mot_de_passe_et_inconnu_meme_message(client, db):
    creer_compte(db, "admin", "admin")
    a = client.post("/auth/login", json={"identifiant": "admin", "password": "faux"})
    b = client.post("/auth/login", json={"identifiant": "inconnu", "password": "faux"})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]


def test_compte_desactive_refuse(client, db):
    user = creer_compte(db, "admin", "admin")
    user.est_actif = False
    db.commit()
    r = client.post("/auth/login", json={"identifiant": "admin", "password": "MotDePasse2026"})
    assert r.status_code == 401


def test_verrouillage_apres_echecs(client, db):
    creer_compte(db, "admin", "admin")
    for _ in range(3):
        assert client.post("/auth/login", json={"identifiant": "admin", "password": "faux"}).status_code == 401
    # Même le bon mot de passe est refusé pendant le verrouillage.
    r = client.post("/auth/login", json={"identifiant": "admin", "password": "MotDePasse2026"})
    assert r.status_code == 429


def test_sans_jeton_ou_jeton_falsifie(client, db):
    creer_compte(db, "admin", "admin")
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer abc.def"}).status_code == 401
    h = connexion(client)
    jeton = h["Authorization"].split()[1]
    falsifie = jeton[:-3] + ("AAA" if not jeton.endswith("AAA") else "BBB")
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {falsifie}"}).status_code == 401


def test_jeton_expire(client, db):
    user = creer_compte(db, "admin", "admin")
    jeton, _ = tokens.creer_jeton(user.id, user.mot_de_passe_hash, duree_heures=-1)
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {jeton}"}).status_code == 401


def test_changement_mot_de_passe_revoque_anciennes_sessions(client, db):
    creer_compte(db, "admin", "admin")
    ancien = connexion(client)
    r = client.post("/auth/mot-de-passe", headers=ancien,
                    json={"ancien_mot_de_passe": "MotDePasse2026", "nouveau_mot_de_passe": "NouveauSecret77"})
    assert r.status_code == 200
    assert client.get("/auth/me", headers=ancien).status_code == 401  # ancienne session révoquée
    neuf = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/auth/me", headers=neuf).status_code == 200


def test_politique_mot_de_passe(client, db):
    creer_compte(db, "admin", "admin")
    h = connexion(client)
    for faible in ["court1", "uniquementdeslettres", "1234567890123"]:
        r = client.post("/auth/mot-de-passe", headers=h,
                        json={"ancien_mot_de_passe": "MotDePasse2026", "nouveau_mot_de_passe": faible})
        assert r.status_code == 400, faible


def test_premiere_connexion_force_le_changement(client, db):
    creer_compte(db, "000101", "salarie", doit_changer=True)
    h = connexion(client, "000101")
    assert client.get("/auth/me", headers=h).status_code == 200
    assert client.get("/admin/utilisateurs", headers=h).status_code == 403  # bloqué tant que non changé
    r = client.post("/auth/mot-de-passe", headers=h,
                    json={"ancien_mot_de_passe": "MotDePasse2026", "nouveau_mot_de_passe": "Salaire2026Ok"})
    assert r.status_code == 200
    assert r.json()["user"]["doit_changer_mot_de_passe"] is False


def test_chiffrement_champs_sensibles():
    clair = "CI93 01011 0123456789 12"
    chiffre = crypto.chiffrer(clair)
    assert chiffre.startswith("enc1:") and clair not in chiffre
    assert crypto.dechiffrer(chiffre) == clair
    assert crypto.chiffrer("") == "" and crypto.chiffrer(None) is None
    assert crypto.masquer("0123456789") == "••••••6789"


def test_en_tetes_de_securite(client):
    r = client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Cache-Control"] == "no-store"
    assert r.headers["X-Frame-Options"] == "DENY"
    _ = time  # (import conservé pour les tests de durée à venir)
