import psycopg2
import pytest

from tests.conftest import TEST_URL, connexion, creer_compte


def test_creation_utilisateur_genere_mot_de_passe_temporaire(client, db):
    creer_compte(db, "admin", "admin")
    h = connexion(client)
    r = client.post("/admin/utilisateurs", headers=h,
                    json={"identifiant": "045700", "nom": "Exemple", "prenom": "Test", "role": "paie"})
    assert r.status_code == 201
    corps = r.json()
    assert corps["utilisateur"]["doit_changer_mot_de_passe"] is True
    assert "lancer_paie" in corps["utilisateur"]["permissions"]  # permissions par défaut du rôle
    # Le mot de passe temporaire fonctionne, une seule fois utile : il impose le changement.
    r2 = client.post("/auth/login", json={"identifiant": "045700", "password": corps["mot_de_passe_temporaire"]})
    assert r2.status_code == 200


def test_identifiant_en_double(client, db):
    creer_compte(db, "admin", "admin")
    h = connexion(client)
    corps = {"identifiant": "000101", "nom": "A", "role": "salarie"}
    assert client.post("/admin/utilisateurs", headers=h, json=corps).status_code == 201
    assert client.post("/admin/utilisateurs", headers=h, json=corps).status_code == 409


def test_route_admin_refusee_sans_permission(client, db):
    creer_compte(db, "000102", "paie", permissions=["lancer_paie"])
    h = connexion(client, "000102")
    assert client.get("/admin/utilisateurs", headers=h).status_code == 403
    assert client.get("/admin/audit", headers=h).status_code == 403


def test_gestionnaire_ne_cree_pas_d_admin(client, db):
    creer_compte(db, "rh", "paie", permissions=["gerer_utilisateurs"])
    h = connexion(client, "rh")
    r = client.post("/admin/utilisateurs", headers=h, json={"identifiant": "x1", "nom": "X", "role": "admin"})
    assert r.status_code == 403


def test_pas_d_elevation_de_privileges_par_les_permissions(client, db):
    creer_compte(db, "rh", "paie", permissions=["gerer_utilisateurs"])
    cible = creer_compte(db, "000103", "salarie")
    h = connexion(client, "rh")
    r = client.put(f"/admin/utilisateurs/{cible.id}/permissions", headers=h, json={"permissions": ["valider_bulletins"]})
    assert r.status_code == 403  # rh n'a pas valider_bulletins : il ne peut pas l'accorder
    ok = client.put(f"/admin/utilisateurs/{cible.id}/permissions", headers=h, json={"permissions": ["gerer_utilisateurs"]})
    assert ok.status_code == 200


def test_permission_inconnue(client, db):
    creer_compte(db, "admin", "admin")
    cible = creer_compte(db, "000104", "salarie")
    h = connexion(client)
    r = client.put(f"/admin/utilisateurs/{cible.id}/permissions", headers=h, json={"permissions": ["n_importe_quoi"]})
    assert r.status_code == 422


def test_dernier_admin_protege(client, db):
    admin = creer_compte(db, "admin", "admin")
    h = connexion(client)
    assert client.patch(f"/admin/utilisateurs/{admin.id}", headers=h, json={"est_actif": False}).status_code == 400
    assert client.patch(f"/admin/utilisateurs/{admin.id}", headers=h, json={"role": "paie"}).status_code == 400
    # Avec un second admin actif, un admin peut en désactiver un autre mais jamais soi-même.
    autre = creer_compte(db, "admin2", "admin")
    assert client.patch(f"/admin/utilisateurs/{admin.id}", headers=h, json={"est_actif": False}).status_code == 400
    assert client.patch(f"/admin/utilisateurs/{autre.id}", headers=h, json={"est_actif": False}).status_code == 200


def test_desactivation_coupe_la_session(client, db):
    creer_compte(db, "admin", "admin")
    cible = creer_compte(db, "000105", "salarie")
    h_admin = connexion(client)
    h_cible = connexion(client, "000105")
    assert client.get("/auth/me", headers=h_cible).status_code == 200
    client.patch(f"/admin/utilisateurs/{cible.id}", headers=h_admin, json={"est_actif": False})
    assert client.get("/auth/me", headers=h_cible).status_code == 401


def test_reinitialisation_mot_de_passe(client, db):
    creer_compte(db, "admin", "admin")
    cible = creer_compte(db, "000106", "salarie")
    h_admin = connexion(client)
    ancien = connexion(client, "000106")
    r = client.post(f"/admin/utilisateurs/{cible.id}/reinitialiser-mot-de-passe", headers=h_admin)
    assert r.status_code == 200
    assert client.get("/auth/me", headers=ancien).status_code == 401  # session révoquée
    nouveau = client.post("/auth/login", json={"identifiant": "000106", "password": r.json()["mot_de_passe_temporaire"]})
    assert nouveau.status_code == 200 and nouveau.json()["user"]["doit_changer_mot_de_passe"] is True


def test_audit_trace_les_actions_sans_secret(client, db):
    creer_compte(db, "admin", "admin")
    h = connexion(client)
    client.post("/admin/utilisateurs", headers=h, json={"identifiant": "000107", "nom": "Z", "role": "salarie"})
    client.post("/auth/login", json={"identifiant": "admin", "password": "mauvais"})
    r = client.get("/admin/audit?taille=50", headers=h)
    assert r.status_code == 200
    actions = [e["action"] for e in r.json()["elements"]]
    assert {"connexion", "connexion_echec", "utilisateur_cree"} <= set(actions)
    brut = r.text
    assert "mauvais" not in brut and "MotDePasse2026" not in brut
    # Filtre par action
    f = client.get("/admin/audit?action=utilisateur_cree", headers=h).json()
    assert f["total"] == 1 and f["elements"][0]["cible_type"] == "utilisateur"


def test_journal_audit_non_modifiable(client, db):
    creer_compte(db, "admin", "admin")
    connexion(client)
    connexion_pg = psycopg2.connect(TEST_URL)
    connexion_pg.autocommit = True
    with connexion_pg.cursor() as c:
        with pytest.raises(psycopg2.Error, match="ajout seul"):
            c.execute("UPDATE journal_audit SET action = 'truque'")
        with pytest.raises(psycopg2.Error, match="ajout seul"):
            c.execute("DELETE FROM journal_audit")
    connexion_pg.close()
