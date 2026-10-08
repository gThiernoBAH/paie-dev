from datetime import date, time
from decimal import Decimal as D

import pytest

from app.core.permissions import PERMISSIONS_PAR_DEFAUT
from app.services import import_pointages, presences
from tests.conftest import connexion, creer_compte


@pytest.fixture
def admin(client, db):
    creer_compte(db)
    return connexion(client)


@pytest.fixture
def salarie(client, admin):
    r = client.post("/salaries", headers=admin, json={"nom": "KONE", "prenoms": "Zie", "matricule": "45724"})
    return r.json()


def pointer(client, h, sid, jour, e, s):
    r = client.put("/pointages", headers=h, json={"salarie_id": sid, "jour": jour, "heure_entree": e, "heure_sortie": s})
    assert r.status_code == 200, r.text
    return r.json()


def semaine_complete(client, h, sid, lundi="2026-02-02", samedi=("08:00", "15:00")):
    for i, jour in enumerate(["02", "03", "04", "05", "06"]):
        pointer(client, h, sid, f"2026-02-{jour}", "08:00", "17:00")   # 9 h - 1 h de pause = 8 h
    if samedi:
        pointer(client, h, sid, "2026-02-07", *samedi)


# --- Calcul des présences ---
def test_semaine_normale_et_hs1(client, db, admin, salarie):
    semaine_complete(client, admin, salarie["id"])
    from app.core.models import Salarie
    r = presences.calculer(db, db.get(Salarie, salarie["id"]), date(2026, 2, 2), date(2026, 2, 8))
    assert r.jours_presence == 6
    assert r.heures_normales == D("40.00")
    assert r.heures_sup == {1: D("6.00"), 2: D(0), 3: D(0), 4: D(0)}   # samedi : 7 h - 1 h de pause = 6 h


def test_hs2_au_dela_de_46_heures(client, db, admin, salarie):
    semaine_complete(client, admin, salarie["id"], samedi=("08:00", "17:00"))   # samedi 8 h
    from app.core.models import Salarie
    r = presences.calculer(db, db.get(Salarie, salarie["id"]), date(2026, 2, 2), date(2026, 2, 8))
    assert r.heures_normales == D("40.00") and r.heures_sup[1] == D("6.00") and r.heures_sup[2] == D("2.00")


def test_dimanche_et_nuit(client, db, admin, salarie):
    pointer(client, admin, salarie["id"], "2026-02-08", "08:00", "12:00")      # dimanche jour : 4 h HS3
    pointer(client, admin, salarie["id"], "2026-02-15", "20:00", "02:00")      # dimanche : 6 h, dont 4 h de nuit
    from app.core.models import Salarie
    r = presences.calculer(db, db.get(Salarie, salarie["id"]), date(2026, 2, 8), date(2026, 2, 21))
    assert r.heures_sup[3] == D("6.00") and r.heures_sup[4] == D("4.00") and r.heures_normales == 0


def test_jour_ferie_compte_comme_dimanche(client, db, admin, salarie):
    pointer(client, admin, salarie["id"], "2026-05-01", "08:00", "12:00")      # 1er mai, vendredi
    from app.core.models import Salarie
    r = presences.calculer(db, db.get(Salarie, salarie["id"]), date(2026, 5, 1), date(2026, 5, 3))
    assert r.heures_sup[3] == D("4.00") and r.heures_normales == 0


def test_cumul_de_semaine_commencee_avant_la_periode(client, db, admin, salarie):
    semaine_complete(client, admin, salarie["id"], samedi=None)                 # 40 h du lundi au vendredi
    pointer(client, admin, salarie["id"], "2026-02-07", "08:00", "13:00")       # samedi 5 h - pas de pause = 5 h
    from app.core.models import Salarie
    # période qui ne commence que le samedi : les 40 h déjà faites comptent
    r = presences.calculer(db, db.get(Salarie, salarie["id"]), date(2026, 2, 7), date(2026, 2, 8))
    assert r.heures_normales == 0 and r.heures_sup[1] == D("5.00")


def test_absences_detectees(client, db, admin, salarie):
    pointer(client, admin, salarie["id"], "2026-02-02", "08:00", "17:00")
    from app.core.models import Salarie
    r = presences.calculer(db, db.get(Salarie, salarie["id"]), date(2026, 2, 2), date(2026, 2, 6))
    assert [j.day for j in r.absences_detectees] == [3, 4, 5, 6]


def test_pointage_incomplet_signale(client, db, admin, salarie):
    pointer(client, admin, salarie["id"], "2026-02-02", "08:00", None)
    from app.core.models import Salarie
    r = presences.calculer(db, db.get(Salarie, salarie["id"]), date(2026, 2, 2), date(2026, 2, 2))
    assert r.jours_presence == 0 and len(r.jours_sans_sortie) == 1


def test_duree_travaillee():
    assert presences.duree_travaillee(time(8, 0), time(17, 0), 60, D(6)) == 480
    assert presences.duree_travaillee(time(8, 0), time(13, 0), 60, D(6)) == 300      # sous le seuil : pas de pause
    assert presences.duree_travaillee(time(22, 0), time(6, 0), 60, D(6)) == 420       # passe minuit


# --- Import ---
def test_import_badgeages(client, admin, salarie):
    csv_ = "Matricule;Date;Heure\n045724;2026-02-02;07:58\n045724;2026-02-02;12:01\n045724;2026-02-02;17:03\n45724;03/02/2026;08:00\n"
    r = client.post("/pointages/import", headers=admin, json={"nom_fichier": "pointeuse.csv", "contenu": csv_}).json()
    assert r["jours_importes"] == 2 and r["nb_rejets"] == 0
    p = client.get("/pointages", headers=admin, params={"du": "2026-02-02", "au": "2026-02-03"}).json()
    assert (p[0]["heure_entree"], p[0]["heure_sortie"]) == ("07:58", "17:03")
    assert (p[1]["heure_entree"], p[1]["heure_sortie"]) == ("08:00", None)         # un seul badgeage : sortie manquante


def test_import_entree_sortie_et_rejets(client, admin, salarie):
    csv_ = "matricule,date,entree,sortie\n045724,2026-02-04,08:00,17:00\n999999,2026-02-04,08:00,17:00\nabc,2026-02-04,08:00,17:00\n045724,pas-une-date,08:00,17:00\n"
    r = client.post("/pointages/import", headers=admin, json={"contenu": csv_}).json()
    assert r["jours_importes"] == 1 and r["nb_rejets"] == 3
    motifs = " | ".join(x["motif"] for x in r["rejets"])
    assert "matricule inconnu 999999" in motifs and "date illisible" in motifs


def test_import_remplace_un_jour_existant(client, admin, salarie):
    pointer(client, admin, salarie["id"], "2026-02-02", "09:00", "10:00")
    client.post("/pointages/import", headers=admin, json={"contenu": "matricule;date;entree;sortie\n045724;2026-02-02;08:00;17:00\n"})
    p = client.get("/pointages", headers=admin, params={"du": "2026-02-02", "au": "2026-02-02"}).json()
    assert len(p) == 1 and p[0]["heure_entree"] == "08:00" and p[0]["source"] == "import"
    assert client.get("/pointages/imports", headers=admin).json()[0]["nb_jours"] == 1


@pytest.mark.parametrize("contenu", ["", "a;b\n1;2\n", "matricule;date\n1;2026-01-01\n"])
def test_import_fichier_invalide(contenu):
    with pytest.raises(import_pointages.FichierInvalide):
        import_pointages.lire(contenu)


# --- API : calcul, jours fériés, rubriques, droits ---
def test_api_calcul_presences(client, admin, salarie):
    semaine_complete(client, admin, salarie["id"])
    r = client.get("/presences/calcul", headers=admin, params={"salarie_id": salarie["id"], "du": "2026-02-02", "au": "2026-02-08"}).json()
    assert r["heures_normales"] == 40 and r["heures_sup"]["1"] == 6 and r["jours_presence"] == 6


def test_jours_feries_et_rubriques(client, admin):
    assert len(client.get("/jours-feries", headers=admin, params={"annee": 2026}).json()) == 10
    assert client.post("/jours-feries", headers=admin, json={"jour": "2026-03-20", "libelle": "Aïd el-Fitr"}).status_code == 201
    assert client.post("/jours-feries", headers=admin, json={"jour": "2026-03-20", "libelle": "x"}).status_code == 409
    assert client.delete("/jours-feries/2026-03-20", headers=admin).status_code == 204
    assert any(r["code"] == "ACO" for r in client.get("/rubriques", headers=admin).json())
    assert client.post("/rubriques", headers=admin, json={"code": "tra", "libelle": "Prime de trajet", "type": "GN"}).status_code == 201
    assert client.post("/rubriques", headers=admin, json={"code": "TRA", "libelle": "x", "type": "GN"}).status_code == 409
    assert client.post("/rubriques", headers=admin, json={"code": "ZZ", "libelle": "x", "type": "XX"}).status_code == 422
    assert client.patch("/rubriques/TRA", headers=admin, json={"est_actif": False}).json()["est_actif"] is False


def test_droits_pointages(client, db, salarie):
    creer_compte(db, "gp", role="paie", permissions=PERMISSIONS_PAR_DEFAUT["paie"])
    creer_compte(db, "dir1", role="direction", permissions=PERMISSIONS_PAR_DEFAUT["direction"])
    gp, dr = connexion(client, "gp"), connexion(client, "dir1")
    assert client.get("/pointages", headers=gp, params={"du": "2026-02-01", "au": "2026-02-02"}).status_code == 200
    assert client.get("/pointages", headers=dr, params={"du": "2026-02-01", "au": "2026-02-02"}).status_code == 403
    assert client.post("/rubriques", headers=dr, json={"code": "X", "libelle": "x", "type": "GN"}).status_code == 403
    assert client.get("/pointages", params={"du": "2026-02-01", "au": "2026-02-02"}).status_code == 401
