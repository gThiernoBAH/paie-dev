"""Lot 12 : clôture annuelle, grille salariale, bulletin paramétrable."""
from decimal import Decimal as D
from io import BytesIO

import pytest
from pypdf import PdfReader
from sqlalchemy import text

from tests.conftest import connexion, creer_compte
from tests.test_octobre_2026 import confirmer, paie, salarie


@pytest.fixture
def admin(client, db):
    creer_compte(db)
    return connexion(client)


def valider(client, db, h, cid):
    confirmer(db)
    r = client.post(f"/campagnes/{cid}/valider", headers=h)
    assert r.status_code == 200, r.text


def _ref(client, h, type_ref, code, libelle):
    r = client.post("/referentiels", headers=h, json={"type_ref": type_ref, "code": code, "libelle": libelle})
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ------------------------------------------------------------------ clôture annuelle
def test_cloture_refusee_sans_paie_validee(client, admin):
    r = client.post("/exercices/2026/cloturer", headers=admin)
    assert r.status_code == 409 and "Aucune paie validée" in r.json()["detail"]


def test_cloture_refusee_si_campagne_non_validee(client, db, admin):
    salarie(client, admin)
    paie(client, db, admin, mois=1)
    r = client.post("/exercices/2026/cloturer", headers=admin)
    assert r.status_code == 409 and "n'est pas validée" in r.json()["detail"]


def test_cloture_fige_les_cumuls_et_verrouille_l_annee(client, db, admin):
    sid = salarie(client, admin)
    cid = paie(client, db, admin, mois=1)
    valider(client, db, admin, cid)
    r = client.post("/exercices/2026/cloturer", headers=admin)
    assert r.status_code == 200 and r.json()["salaries"] == 1
    d = client.get("/exercices/2026", headers=admin).json()
    assert d["statut"] == "cloture" and len(d["instantane"]["lignes"]) == 1
    assert client.get(f"/campagnes/{cid}", headers=admin).json()["statut"] == "cloturee"
    # verrou : campagne, salaire, augmentation
    assert client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 2}).status_code == 409
    assert client.post(f"/salaries/{sid}/salaires", headers=admin, json={"date_effet": "2026-06-01", "montant": 250000, "sursalaire": 0}).status_code == 409
    a = client.post("/augmentations", headers=admin, json={"libelle": "Test", "mode": "pourcentage", "valeur": 5, "date_effet": "2026-07-01"})
    assert a.status_code == 422 and "clôturé" in a.json()["detail"]
    # une autre année reste libre
    assert client.post(f"/salaries/{sid}/salaires", headers=admin, json={"date_effet": "2027-01-01", "montant": 250000, "sursalaire": 0}).status_code == 201
    # double clôture refusée
    assert client.post("/exercices/2026/cloturer", headers=admin).status_code == 409


def test_reouverture_reservee_a_l_admin_avec_motif(client, db, admin):
    salarie(client, admin)
    cid = paie(client, db, admin, mois=1)
    valider(client, db, admin, cid)
    client.post("/exercices/2026/cloturer", headers=admin)
    creer_compte(db, "valideur", "paie")
    db.execute(text("INSERT INTO permissions_utilisateurs (utilisateur_id, permission) SELECT id, 'valider_bulletins' FROM utilisateurs WHERE identifiant = 'valideur' ON CONFLICT DO NOTHING"))
    db.commit()
    h = connexion(client, "valideur")
    assert client.post("/exercices/2026/rouvrir", headers=h, json={"motif": "Erreur de saisie"}).status_code == 403
    assert client.post("/exercices/2026/rouvrir", headers=admin, json={"motif": "ab"}).status_code == 422
    r = client.post("/exercices/2026/rouvrir", headers=admin, json={"motif": "Erreur de saisie détectée"})
    assert r.status_code == 200 and r.json()["statut"] == "rouvert"
    assert client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 2}).status_code == 201
    actions = {a["action"] for a in client.get("/admin/audit", headers=admin, params={"taille": 50}).json()["elements"]}
    assert {"exercice_cloture", "exercice_rouvert"} <= actions


def test_liste_des_exercices(client, db, admin):
    salarie(client, admin)
    paie(client, db, admin, mois=1)
    l = client.get("/exercices", headers=admin).json()
    e = next(x for x in l if x["annee"] == 2026)
    assert e["statut"] == "ouvert" and e["campagnes"] == 1 and e["campagnes_validees"] == 0 and e["raisons"]


# ------------------------------------------------------------------ grille salariale
def _grille(client, h):
    cat = _ref(client, h, "categorie", "1A", "1 A")
    r = client.put(f"/grille/categories/{cat}", headers=h, json={"date_effet": "2026-01-01", "base_horaire": 667.53})
    assert r.status_code == 200, r.text
    return cat


def test_salaires_par_tranche_comme_le_legacy(client, admin):
    _grille(client, admin)
    ligne = next(c for c in client.get("/grille/categories", headers=admin).json() if c["code"] == "1A")
    # image du legacy : 1 A → 115 703 / 129 009 / 132 335 / 142 315 / 66 529
    attendu = [115703, 129009, 132335, 142315, 66529]
    assert all(abs(float(x) - a) <= 2 for x, a in zip(ligne["salaires"], attendu))


def test_base_datee(client, admin):
    cat = _grille(client, admin)
    client.put(f"/grille/categories/{cat}", headers=admin, json={"date_effet": "2027-01-01", "base_horaire": 700})
    avant = next(c for c in client.get("/grille/categories", headers=admin, params={"date_effet": "2026-06-01"}).json() if c["code"] == "1A")
    apres = next(c for c in client.get("/grille/categories", headers=admin, params={"date_effet": "2027-06-01"}).json() if c["code"] == "1A")
    assert float(avant["base_horaire"]) == 667.53 and float(apres["base_horaire"]) == 700


def test_tranches_modifiables(client, admin):
    t = client.get("/grille/tranches", headers=admin).json()
    assert len(t) == 5
    t[0]["heures"] = 170
    r = client.put("/grille/tranches", headers=admin, json=[{"numero": x["numero"], "libelle": x["libelle"], "heures": float(x["heures"]), "coefficient": float(x["coefficient"])} for x in t])
    assert r.status_code == 200 and float(r.json()[0]["heures"]) == 170


def test_position_du_salarie_et_avertissement(client, admin):
    cat = _grille(client, admin)
    sid = salarie(client, admin, categorie_id=cat, tranche=1, salaire_base=100000)
    p = client.get(f"/salaries/{sid}/grille", headers=admin).json()
    assert p["statut"] == "sous_grille" and abs(float(p["salaire_grille"]) - 115703) <= 2
    # un salaire au niveau de la grille : conforme
    client.post(f"/salaries/{sid}/salaires", headers=admin, json={"date_effet": "2026-06-01", "montant": 115703, "sursalaire": 0})
    assert client.get(f"/salaries/{sid}/grille", headers=admin).json()["statut"] == "conforme"
    # sans tranche : sans grille
    autre = salarie(client, admin, nom="DIA", categorie_id=cat)
    assert client.get(f"/salaries/{autre}/grille", headers=admin).json()["statut"] == "sans_grille"


def test_blocage_sous_minimum_si_parametre_actif(client, admin):
    cat = _grille(client, admin)
    sid = salarie(client, admin, categorie_id=cat, tranche=1, salaire_base=120000)
    r = client.get("/parametres", headers=admin)
    assert any(p["cle"] == "grille_blocage_sous_minimum" for p in (r.json() if isinstance(r.json(), list) else r.json().get("elements", [])))
    r = client.post("/parametres/grille_blocage_sous_minimum/valeurs", headers=admin,
                    json={"valeur": "true", "date_effet": "2026-01-01", "source": "Décision de la direction"})
    assert r.status_code in (200, 201), r.text
    refus = client.post(f"/salaries/{sid}/salaires", headers=admin, json={"date_effet": "2026-06-01", "montant": 110000, "sursalaire": 0})
    assert refus.status_code == 422 and "grille" in refus.json()["detail"]
    ok = client.post(f"/salaries/{sid}/salaires", headers=admin, json={"date_effet": "2026-06-01", "montant": 116000, "sursalaire": 0})
    assert ok.status_code == 201


LEGACY = "CATEGORIE\tLIBELLE\tNB SALARIES\tBASE HEURE\tSALAIRE MENSUEL TRANCHE 1\n1\t1ERE CATEGORIES\t0\t346,16\t60 000\n1 A\t1 A\t0\t667,53\t115 703\nZZ\tInconnue\t0\t10\t1\n"


def test_import_depuis_le_legacy(client, admin):
    c1 = _ref(client, admin, "categorie", "1", "1ERE CATEGORIES")
    c2 = _ref(client, admin, "categorie", "1A", "1 A")
    apercu = client.post("/grille/import", headers=admin, json={"contenu": LEGACY, "date_effet": "2026-01-01", "appliquer": False}).json()
    assert apercu["ok"] == 2 and apercu["ignorees"] == 1 and apercu["appliquees"] == 0
    assert next(c for c in client.get("/grille/categories", headers=admin).json() if c["categorie_id"] == c2)["base_horaire"] is None
    r = client.post("/grille/import", headers=admin, json={"contenu": LEGACY, "date_effet": "2026-01-01", "appliquer": True}).json()
    assert r["appliquees"] == 2
    lignes = {c["categorie_id"]: c for c in client.get("/grille/categories", headers=admin).json()}
    assert float(lignes[c2]["base_horaire"]) == 667.53 and round(float(lignes[c1]["salaires"][0])) == 60000


def test_import_deduit_la_base_du_salaire_tranche_1(client, admin):
    c = _ref(client, admin, "categorie", "7B", "7 B")
    contenu = "CATEGORIE;SALAIRE MENSUEL TRANCHE 1\n7B;120 480\n"
    r = client.post("/grille/import", headers=admin, json={"contenu": contenu, "date_effet": "2026-01-01", "appliquer": True}).json()
    assert r["appliquees"] == 1
    ligne = next(x for x in client.get("/grille/categories", headers=admin).json() if x["categorie_id"] == c)
    assert round(float(ligne["salaires"][0])) == 120480


def test_import_colonne_manquante(client, admin):
    r = client.post("/grille/import", headers=admin, json={"contenu": "A;B\n1;2\n", "date_effet": "2026-01-01"})
    assert r.status_code == 422


def test_rapport_hors_grille_et_droits(client, db, admin):
    cat = _grille(client, admin)
    salarie(client, admin, categorie_id=cat, tranche=1, salaire_base=100000)
    r = client.get("/rapports/hors-grille", headers=admin, params={"format": "json"})
    assert r.status_code == 200 and r.json()["lignes"][0][-1] == "Sous la grille"
    creer_compte(db, "lecteur", "direction")
    h = connexion(client, "lecteur")
    assert client.get("/grille/categories", headers=h).status_code == 403
    assert client.put(f"/grille/categories/{cat}", headers=h, json={"date_effet": "2026-01-01", "base_horaire": 1}).status_code == 403


# ------------------------------------------------------------------ bulletin paramétrable
def _texte_pdf(client, h, cid):
    bid = client.get(f"/campagnes/{cid}/bulletins", headers=h).json()[0]["id"]
    r = client.get(f"/bulletins/{bid}/pdf", headers=h)
    assert r.status_code == 200
    return PdfReader(BytesIO(r.content)).pages[0].extract_text()


def _regler(client, h, cle, valeur):
    r = client.post(f"/parametres/{cle}/valeurs", headers=h, json={"valeur": valeur, "date_effet": "2026-01-01", "source": "Séance paie"})
    assert r.status_code in (200, 201), r.text


def test_bulletin_par_defaut_inchange(client, db, admin):
    salarie(client, admin)
    t = _texte_pdf(client, admin, paie(client, db, admin))
    assert "Conservez ce bulletin sans limitation de durée." in t and "Arrêté le présent bulletin" in t and "Cumuls" not in t
    assert "Emploi" in t and "Solde au" not in t


def test_bulletin_options(client, db, admin):
    salarie(client, admin)
    cid = paie(client, db, admin)
    for cle, v in [("bulletin_afficher_cumuls", "true"), ("bulletin_afficher_conges", "true"), ("bulletin_afficher_charges_patronales", "true"),
                   ("bulletin_afficher_net_en_lettres", "false"), ("bulletin_afficher_identite_emploi", "false"),
                   ("bulletin_mentions_legales", "-"), ("bulletin_pied_de_page", "SIVOP – Abidjan, Zone 4")]:
        _regler(client, admin, cle, v)
    t = _texte_pdf(client, admin, cid)
    assert "Cumuls 2026" in t and "Solde au" in t and "Charges patronales" in t
    assert "Arrêté le présent bulletin" not in t and "Emploi" not in t
    assert "Conservez ce bulletin" not in t and "Abidjan, Zone 4" in t


def test_cumuls_sur_le_bulletin_additionnent_les_mois(client, db, admin):
    salarie(client, admin)
    c1 = paie(client, db, admin, mois=1)
    valider(client, db, admin, c1)
    c2 = paie(client, db, admin, mois=2)
    _regler(client, admin, "bulletin_afficher_cumuls", "true")
    b = client.get(f"/campagnes/{c2}/bulletins", headers=admin).json()[0]
    net_mois = D(str(b["net_a_payer"]))
    from app.exports.bulletin_pdf import _fcfa
    assert _fcfa(net_mois * 2) in _texte_pdf(client, admin, c2).replace("\xa0", " ")
