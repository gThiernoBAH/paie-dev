import pytest

from app.core.permissions import PERMISSIONS_PAR_DEFAUT
from app.services import salaries as svc
from tests.conftest import connexion, creer_compte


@pytest.fixture
def admin(client, db):
    creer_compte(db)
    return connexion(client)


@pytest.fixture
def gestionnaire(client, db):
    """Gestionnaire de paie SANS droit sur les données sensibles (cas courant)."""
    creer_compte(db, "gp", role="paie", permissions=PERMISSIONS_PAR_DEFAUT["paie"])
    return connexion(client, "gp")


def _ref(client, h, type_ref, code, libelle="Libellé"):
    r = client.post("/referentiels", headers=h, json={"type_ref": type_ref, "code": code, "libelle": libelle})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _salarie(client, h, **plus):
    r = client.post("/salaries", headers=h, json={"nom": "KOUASSI", "prenoms": "Awa", **plus})
    assert r.status_code == 201, r.text
    return r.json()


# --- Règles pures ---
def test_matricule_normalise():
    assert svc.normaliser_matricule("54") == "000054"
    assert svc.normaliser_matricule("045700") == "045700"
    for mauvais in ("", "abc", "1234567", "12 3"):
        with pytest.raises(svc.MatriculeInvalide):
            svc.normaliser_matricule(mauvais)


@pytest.mark.parametrize("situation,enfants,attendu", [
    ("celibataire", 0, 1), ("marie", 0, 2), ("marie", 3, 3.5), ("celibataire", 1, 2),
    ("divorce", 3, 3), ("veuf", 0, 1), ("marie", 20, 5),
])
def test_parts(situation, enfants, attendu):
    assert float(svc.parts_suggerees(situation, enfants)) == attendu


# --- Référentiels ---
def test_referentiels(client, admin):
    assert len(client.get("/referentiels", headers=admin, params={"type_ref": "banque"}).json()) >= 10
    rid = _ref(client, admin, "service", "exp", "Expédition")
    assert client.post("/referentiels", headers=admin, json={"type_ref": "service", "code": "EXP", "libelle": "x"}).status_code == 409
    assert client.post("/referentiels", headers=admin, json={"type_ref": "autre", "code": "A", "libelle": "x"}).status_code == 422
    assert client.patch(f"/referentiels/{rid}", headers=admin, json={"est_actif": False}).status_code == 200
    assert not any(r["id"] == rid for r in client.get("/referentiels", headers=admin, params={"type_ref": "service"}).json())
    assert any(r["id"] == rid for r in client.get("/referentiels", headers=admin, params={"type_ref": "service", "inclure_inactifs": True}).json())


# --- Fiche salarié ---
def test_creation_matricule_automatique(client, admin):
    assert _salarie(client, admin)["matricule"] == "000001"
    assert _salarie(client, admin, matricule="54")["matricule"] == "000054"
    assert _salarie(client, admin)["matricule"] == "000055"
    assert client.post("/salaries", headers=admin, json={"nom": "X", "matricule": "54"}).status_code == 409
    assert client.post("/salaries", headers=admin, json={"nom": "X", "matricule": "ab"}).status_code == 422
    assert client.get("/salaries/prochain-matricule", headers=admin).json() == {"matricule": "000056"}


def test_parts_calculees_a_la_creation_et_a_la_modification(client, admin):
    s = _salarie(client, admin, situation_matrimoniale="marie", nombre_enfants=2)
    assert s["nombre_parts"] == 3
    s2 = client.patch(f"/salaries/{s['id']}", headers=admin, json={"nombre_enfants": 3}).json()
    assert s2["nombre_parts"] == 3.5
    s3 = client.patch(f"/salaries/{s['id']}", headers=admin, json={"nombre_parts": 4, "nombre_enfants": 4}).json()
    assert s3["nombre_parts"] == 4  # la valeur saisie à la main l'emporte


def test_liens_referentiels_controles(client, admin):
    banque = client.get("/referentiels", headers=admin, params={"type_ref": "banque"}).json()[0]["id"]
    svc_id = _ref(client, admin, "service", "EXP")
    s = _salarie(client, admin, service_id=svc_id, banque_id=banque)
    assert s["service"]["code"] == "EXP"
    assert client.post("/salaries", headers=admin, json={"nom": "X", "service_id": banque}).status_code == 422   # mauvais type
    assert client.post("/salaries", headers=admin, json={"nom": "X", "service_id": 99999}).status_code == 422
    client.patch(f"/referentiels/{svc_id}", headers=admin, json={"est_actif": False})
    assert client.post("/salaries", headers=admin, json={"nom": "X", "service_id": svc_id}).status_code == 422   # inactif


def test_liste_filtres_pagination(client, admin):
    svc_id = _ref(client, admin, "service", "EXP")
    for i in range(5):
        _salarie(client, admin, service_id=svc_id if i < 2 else None, type_remuneration="journalier" if i == 4 else "mensuel")
    r = client.get("/salaries", headers=admin, params={"taille": 2, "page": 2}).json()
    assert r["total"] == 5 and len(r["elements"]) == 2 and r["elements"][0]["matricule"] == "000003"
    assert client.get("/salaries", headers=admin, params={"service_id": svc_id}).json()["total"] == 2
    assert client.get("/salaries", headers=admin, params={"type_remuneration": "journalier"}).json()["total"] == 1
    assert client.get("/salaries", headers=admin, params={"recherche": "000003"}).json()["total"] == 1
    assert client.get("/salaries", headers=admin, params={"recherche": "kouas"}).json()["total"] == 5


# --- Données sensibles ---
def test_donnees_sensibles_chiffrees_en_base(client, db, admin):
    from app.core.models import Salarie
    s = _salarie(client, admin, rib="ci008 01234 012345678901 23", numero_cnps="0123456", salaire_base=250000)
    brut = db.get(Salarie, s["id"])
    assert brut.rib_chiffre.startswith("enc1:") and "CI008" not in brut.rib_chiffre
    assert brut.numero_cnps_chiffre.startswith("enc1:") and "0123456" not in brut.numero_cnps_chiffre
    r = client.get(f"/salaries/{s['id']}/donnees-sensibles", headers=admin).json()
    assert r == {"rib": "CI0080123401234567890123", "numero_cnps": "0123456"}
    assert s["salaire_actuel"]["montant"] == 250000


def test_sans_droit_sensible_rien_ne_fuit(client, db, admin, gestionnaire):
    s = _salarie(client, admin, rib="CI0080123401234567890123", numero_cnps="0123456", salaire_base=250000)
    f = client.get(f"/salaries/{s['id']}", headers=gestionnaire).json()
    assert f["salaire_actuel"] is None and f["donnees_sensibles_visibles"] is False
    assert f["a_un_rib"] is True
    assert "rib" not in f and "CI008" not in str(f) and "0123456" not in str(f)
    assert client.get(f"/salaries/{s['id']}/donnees-sensibles", headers=gestionnaire).status_code == 403
    assert client.get(f"/salaries/{s['id']}/salaires", headers=gestionnaire).status_code == 403
    assert client.post("/salaries", headers=gestionnaire, json={"nom": "Z", "salaire_base": 1}).status_code == 403
    assert client.patch(f"/salaries/{s['id']}", headers=gestionnaire, json={"rib": "CI0080123401234567890123"}).status_code == 403
    assert client.patch(f"/salaries/{s['id']}", headers=gestionnaire, json={"ville": "Abidjan"}).status_code == 200


def test_consultation_sensible_tracee_sans_valeurs(client, admin):
    s = _salarie(client, admin, rib="CI0080123401234567890123")
    client.get(f"/salaries/{s['id']}/donnees-sensibles", headers=admin)
    client.patch(f"/salaries/{s['id']}", headers=admin, json={"rib": "CI0080123401234567890199", "ville": "Yopougon"})
    audit = client.get("/admin/audit", headers=admin, params={"taille": 200}).json()["elements"]
    actions = [a["action"] for a in audit]
    assert "salarie_donnees_sensibles_consultees" in actions
    modif = next(a for a in audit if a["action"] == "salarie_modifie")
    assert modif["detail"]["champs"] == ["rib", "ville"]
    assert "CI008" not in str(audit)


def test_rib_invalide(client, admin):
    assert client.post("/salaries", headers=admin, json={"nom": "X", "rib": "123"}).status_code == 422


def test_efface_le_rib(client, admin):
    s = _salarie(client, admin, rib="CI0080123401234567890123")
    f = client.patch(f"/salaries/{s['id']}", headers=admin, json={"rib": None}).json()
    assert f["a_un_rib"] is False


# --- Salaire daté ---
def test_historique_salaire(client, admin):
    s = _salarie(client, admin, date_embauche="2024-01-01", salaire_base=200000)
    sid = s["id"]
    r = client.post(f"/salaries/{sid}/salaires", headers=admin, json={"date_effet": "2026-01-01", "montant": 300000, "motif": "Promotion"})
    assert r.status_code == 201 and [e["montant"] for e in r.json()] == [300000, 200000]
    assert client.post(f"/salaries/{sid}/salaires", headers=admin, json={"date_effet": "2026-01-01", "montant": 1}).status_code == 409
    assert client.get(f"/salaries/{sid}", headers=admin).json()["salaire_actuel"]["montant"] == 300000
    # un salaire futur n'est pas encore en vigueur
    client.post(f"/salaries/{sid}/salaires", headers=admin, json={"date_effet": "2099-01-01", "montant": 999999})
    assert client.get(f"/salaries/{sid}", headers=admin).json()["salaire_actuel"]["montant"] == 300000


# --- Sortie et compte ---
def test_sortie_desactive_le_compte(client, db, admin):
    s = _salarie(client, admin, date_embauche="2024-01-01", email="awa@example.ci")
    c = client.post(f"/salaries/{s['id']}/creer-compte", headers=admin)
    assert c.status_code == 201 and c.json()["utilisateur"]["identifiant"] == s["matricule"]
    assert client.post(f"/salaries/{s['id']}/creer-compte", headers=admin).status_code == 409
    mdp = c.json()["mot_de_passe_temporaire"]
    assert client.post("/auth/login", json={"identifiant": s["matricule"], "password": mdp}).status_code == 200
    assert client.post(f"/salaries/{s['id']}/sortie", headers=admin, json={"date_sortie": "2023-01-01", "motif_sortie": "démission"}).status_code == 422
    r = client.post(f"/salaries/{s['id']}/sortie", headers=admin, json={"date_sortie": "2026-09-30", "motif_sortie": "démission"})
    assert r.status_code == 200 and r.json()["est_actif"] is False
    assert client.post("/auth/login", json={"identifiant": s["matricule"], "password": mdp}).status_code == 401
    assert client.get("/salaries", headers=admin).json()["total"] == 0
    assert client.get("/salaries", headers=admin, params={"statut": "sortis"}).json()["total"] == 1
    assert client.post(f"/salaries/{s['id']}/reactiver", headers=admin).json()["est_actif"] is True


def test_droits(client, db, admin):
    creer_compte(db, "salarie1", role="salarie")
    h = connexion(client, "salarie1")
    assert client.get("/salaries", headers=h).status_code == 403
    assert client.get("/referentiels", headers=h).status_code == 403
    assert client.post("/salaries", headers=h, json={"nom": "X"}).status_code == 403
    assert client.get("/salaries").status_code == 401


def test_sursalaire_et_transport(client, admin):
    s = _salarie(client, admin, salaire_base=135540, sursalaire=69899, indemnite_transport=38102, date_embauche="2024-01-01")
    assert s["salaire_actuel"] == {"montant": 135540, "sursalaire": 69899, "date_effet": "2024-01-01"}
    assert s["indemnite_transport"] == 38102
    r = client.post(f"/salaries/{s['id']}/salaires", headers=admin, json={"date_effet": "2026-01-01", "montant": 140000, "sursalaire": 70000})
    assert r.json()[0]["sursalaire"] == 70000
