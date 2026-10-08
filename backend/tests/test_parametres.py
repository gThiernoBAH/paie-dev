from datetime import date
from decimal import Decimal

import psycopg2
import pytest

from app.services import parametres as svc
from tests.conftest import TEST_URL, connexion, creer_compte


@pytest.fixture
def admin(client, db):
    creer_compte(db)
    return connexion(client)


def _valeur(client, h, cle, valeur, jour="2026-07-01", statut="confirme", source="Note de service 12/2026"):
    return client.post(f"/parametres/{cle}/valeurs", headers=h,
                       json={"valeur": valeur, "date_effet": jour, "statut": statut, "source": source})


# --- Lecture par le moteur ---
def test_lecture_typee(db):
    assert svc.lire(db, "smig_mensuel") == Decimal("75000")
    assert svc.lire(db, "anciennete_seuil_mois") == 25
    assert svc.lire(db, "nuit_debut") == "22:00"
    bareme = svc.lire(db, "its_bareme_mensuel")
    assert bareme[0] == {"jusqu_a": Decimal(75000), "taux": Decimal(0)}
    assert bareme[-1] == {"jusqu_a": None, "taux": Decimal(32)}


def test_inconnu(db):
    with pytest.raises(svc.ParametreIntrouvable):
        svc.lire(db, "n_existe_pas")


def test_valeur_datee_selon_la_date(client, db, admin):
    assert _valeur(client, admin, "smig_mensuel", "80000", "2026-07-01").status_code == 201
    assert svc.lire(db, "smig_mensuel", date(2026, 6, 30)) == Decimal("75000")
    assert svc.lire(db, "smig_mensuel", date(2026, 7, 1)) == Decimal("80000")
    assert svc.lire(db, "smig_mensuel", date(2030, 1, 1)) == Decimal("80000")


# --- Validation ---
@pytest.mark.parametrize("cle,valeur", [
    ("smig_mensuel", "abc"), ("smig_mensuel", "-5"), ("anciennete_seuil_mois", "2.5"),
    ("cnps_taux_retraite_salarie", "101"), ("nuit_debut", "25:00"), ("mode_arrondi_cotisations", "au hasard"),
    ("its_bareme_mensuel", "pas du json"), ("its_bareme_mensuel", "[]"),
    ("its_bareme_mensuel", '[{"jusqu_a": 100, "taux": 10}]'),                                   # dernière tranche bornée
    ("its_bareme_mensuel", '[{"jusqu_a": 200, "taux": 10}, {"jusqu_a": 100, "taux": 20}, {"jusqu_a": null, "taux": 30}]'),
    ("its_bareme_mensuel", '[{"jusqu_a": 100, "taux": 150}, {"jusqu_a": null, "taux": 30}]'),
])
def test_valeurs_refusees(client, admin, cle, valeur):
    assert _valeur(client, admin, cle, valeur).status_code == 422


def test_normalisation(client, admin):
    r = _valeur(client, admin, "cnps_taux_retraite_salarie", "6,30")  # virgule française acceptée
    assert r.status_code == 201
    assert r.json()["valeur_courante"]["valeur"] == "6.3"
    r = _valeur(client, admin, "smig_mensuel", "80 000", "2026-08-01")
    assert r.json()["valeur_courante"]["valeur"] == "80000"


def test_bareme_valide(client, admin, db):
    b = '[{"jusqu_a": 100000, "taux": 0}, {"jusqu_a": null, "taux": 10.5}]'
    assert _valeur(client, admin, "its_bareme_mensuel", b, "2027-01-01").status_code == 201
    assert svc.lire(db, "its_bareme_mensuel", date(2027, 2, 1))[1]["taux"] == Decimal("10.5")


# --- Règles de gestion de l'historique ---
def test_confirmer_exige_une_source(client, admin):
    r = _valeur(client, admin, "smig_mensuel", "80000", source="")
    assert r.status_code == 422
    assert _valeur(client, admin, "smig_mensuel", "80000", statut="a_confirmer", source="").status_code == 201


def test_valeur_confirmee_ne_s_ecrase_pas(client, admin):
    assert _valeur(client, admin, "smig_mensuel", "80000", "2026-07-01").status_code == 201
    assert _valeur(client, admin, "smig_mensuel", "81000", "2026-07-01").status_code == 409


def test_valeur_a_confirmer_se_corrige(client, admin):
    assert _valeur(client, admin, "smig_mensuel", "80000", "2026-07-01", statut="a_confirmer").status_code == 201
    r = _valeur(client, admin, "smig_mensuel", "81000", "2026-07-01")
    assert r.status_code == 201
    assert r.json()["valeur_courante"]["valeur"] == "81000"
    assert len([v for v in r.json()["historique"] if v["date_effet"] == "2026-07-01"]) == 1


def test_confirmer_une_valeur_existante(client, admin):
    d = client.get("/parametres/cnps_taux_accident_travail", headers=admin).json()
    v = d["valeur_courante"]
    assert v["statut"] == "a_confirmer"
    assert client.post(f"/parametres/{d['cle']}/valeurs/{v['id']}/confirmer", headers=admin, json={"source": "ab"}).status_code == 422
    r = client.post(f"/parametres/{d['cle']}/valeurs/{v['id']}/confirmer", headers=admin, json={"source": "Notification CNPS 2026"})
    assert r.status_code == 200
    assert r.json()["valeur_courante"]["statut"] == "confirme"
    assert r.json()["valeur_courante"]["confirme_par"] == "admin"
    assert client.post(f"/parametres/{d['cle']}/valeurs/{v['id']}/confirmer", headers=admin, json={"source": "Notification CNPS 2026"}).status_code == 409


def test_etat_et_filtres(client, admin):
    e = client.get("/parametres/etat", headers=admin).json()
    assert e["total"] == 54 and e["a_confirmer"] > 0 and e["critiques_a_confirmer"] > 0
    assert "fdfp_taux_formation_continue" in e["cles_critiques"]
    assert "smig_mensuel" not in e["cles_critiques"]
    lst = client.get("/parametres", headers=admin, params={"statut": "a_confirmer"}).json()
    assert len(lst) == e["a_confirmer"]
    assert {p["categorie"] for p in client.get("/parametres", headers=admin, params={"categorie": "its"}).json()} == {"its"}
    assert all("smig" in p["cle"] for p in client.get("/parametres", headers=admin, params={"recherche": "smig"}).json())


def test_confirmer_tout_leve_le_blocage(client, admin, db):
    for cle in client.get("/parametres/etat", headers=admin).json()["cles_critiques"]:
        v = client.get(f"/parametres/{cle}", headers=admin).json()["valeur_courante"]
        assert client.post(f"/parametres/{cle}/valeurs/{v['id']}/confirmer", headers=admin, json={"source": "Revue paie"}).status_code == 200
    assert svc.critiques_a_confirmer(db) == []


# --- Droits et audit ---
def test_droits(client, db, admin):
    creer_compte(db, "lecteur", role="direction", permissions=["voir_parametres"])
    h = connexion(client, "lecteur")
    assert client.get("/parametres", headers=h).status_code == 200
    assert _valeur(client, h, "smig_mensuel", "80000").status_code == 403
    creer_compte(db, "salarie1", role="salarie")
    h2 = connexion(client, "salarie1")
    assert client.get("/parametres", headers=h2).status_code == 403
    assert client.get("/parametres").status_code == 401


def test_responsable_paie_peut_modifier(client, db):
    from app.core.permissions import PERMISSIONS_PAR_DEFAUT
    creer_compte(db, "gp", role="paie", permissions=PERMISSIONS_PAR_DEFAUT["paie"])
    h = connexion(client, "gp")
    assert _valeur(client, h, "smig_mensuel", "80000").status_code == 201


def test_audit(client, admin):
    _valeur(client, admin, "smig_mensuel", "80000")
    lignes = client.get("/admin/audit", headers=admin, params={"action": "parametre_valeur_ajoutee"}).json()["elements"]
    assert len(lignes) == 1
    assert lignes[0]["cible_id"] == "smig_mensuel" and lignes[0]["detail"]["valeur"] == "80000"


def test_inconnu_404(client, admin):
    assert client.get("/parametres/xxx", headers=admin).status_code == 404
    assert _valeur(client, admin, "xxx", "1").status_code == 404


def test_seed_rejouable_sans_ecraser(client, admin):
    assert _valeur(client, admin, "cnps_taux_accident_travail", "2", "2000-01-01", statut="a_confirmer").status_code == 201
    from tests.conftest import PARAMS
    c = psycopg2.connect(TEST_URL)
    c.autocommit = True
    c.cursor().execute(PARAMS.read_text(encoding="utf-8"))
    c.close()
    assert client.get("/parametres/cnps_taux_accident_travail", headers=admin).json()["valeur_courante"]["valeur"] == "2"
