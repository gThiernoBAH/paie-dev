"""Évolutions d'octobre 2026 : statistiques, enfants, rubriques fixes, augmentations en masse, simulation, journaux, congés."""
from datetime import date
from decimal import Decimal as D

import pytest
from sqlalchemy import text

from app.core.permissions import PERMISSIONS_PAR_DEFAUT
from app.services.statistiques import tranche_age
from tests.conftest import connexion, creer_compte


@pytest.fixture
def admin(client, db):
    creer_compte(db)
    return connexion(client)


def confirmer(db):
    db.execute(text("UPDATE valeurs_parametres SET statut = 'confirme'"))
    db.commit()


def salarie(client, h, **plus):
    base = {"nom": "KONE", "date_embauche": "2021-01-01", "salaire_base": 200000}
    r = client.post("/salaries", headers=h, json={**base, **plus})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def paie(client, db, h, mois=3, annee=2026):
    """Crée (ou retrouve) la campagne mensuelle du mois, l'initialise et la (re)calcule."""
    r = client.post("/campagnes", headers=h, json={"type_campagne": "mensuelle", "annee": annee, "mois": mois})
    if r.status_code == 201:
        cid = r.json()["id"]
    else:
        cid = next(c["id"] for c in client.get("/campagnes", headers=h).json() if c["annee"] == annee and c["mois"] == mois)
    client.post(f"/campagnes/{cid}/initialiser", headers=h)
    client.post(f"/campagnes/{cid}/calculer", headers=h)
    return cid


def net(client, h, cid, matricule):
    b = next(b for b in client.get(f"/campagnes/{cid}/bulletins", headers=h).json() if b["matricule"] == matricule)
    return D(str(b["net_a_payer"]))


def lignes_bulletin(client, h, cid, matricule):
    b = next(b for b in client.get(f"/campagnes/{cid}/bulletins", headers=h).json() if b["matricule"] == matricule)
    return {l["code"]: l for l in client.get(f"/bulletins/{b['id']}", headers=h).json()["lignes"]}


# ------------------------------------------------------------------ statistiques
def test_tranches_d_age_sans_trou():
    assert [tranche_age(a) for a in (18, 25, 26, 35, 36, 45, 46, 60)] == [
        "25 ans et moins", "25 ans et moins", "26-35 ans", "26-35 ans", "36-45 ans", "36-45 ans", "46 ans et plus", "46 ans et plus"]
    assert tranche_age(None) == "Non renseigné"


@pytest.fixture
def paie_validee(client, db, admin):
    for code, lib in (("EXP", "Exploitation"), ("ADM", "Administration")):
        client.post("/referentiels", headers=admin, json={"type_ref": "service", "code": code, "libelle": lib})
    services = {r["code"]: r["id"] for r in client.get("/referentiels?type_ref=service", headers=admin).json()}
    annee = date.today().year
    for mat, serv, base, sexe, naiss in (("1", "EXP", 200000, "M", f"{annee - 25}-01-01"), ("2", "EXP", 300000, "F", f"{annee - 40}-06-15"),
                                         ("3", "ADM", 400000, "F", None)):
        salarie(client, admin, nom=f"N{mat}", matricule=mat, salaire_base=base, service_id=services[serv], sexe=sexe, date_naissance=naiss)
    cid = paie(client, db, admin, mois=1, annee=annee)
    confirmer(db)
    assert client.post(f"/campagnes/{cid}/valider", headers=admin).status_code == 200
    return services


def test_statistiques_effectifs_et_masse(client, admin, paie_validee):
    r = client.get("/tableau-de-bord/statistiques", headers=admin)
    assert r.status_code == 200, r.text
    j = r.json()
    e, m = j["effectifs"], j["masse"]
    assert e["kpi"]["effectif"] == 3
    assert dict(zip(e["sexe"]["labels"], e["sexe"]["valeurs"])) == {"Femmes": 2, "Hommes": 1}
    assert dict(zip(e["services"]["labels"], e["services"]["valeurs"])) == {"Exploitation": 2, "Administration": 1}
    assert dict(zip(e["tranches_age"]["labels"], e["tranches_age"]["valeurs"])) == {"25 ans et moins": 1, "36-45 ans": 1, "Non renseigné": 1}
    assert len(m["evolution"]["net"]) == 12 and m["evolution"]["net"][0] > 0 and sum(m["evolution"]["net"][1:]) == 0
    assert m["effectif_paye"]["valeurs"][0] == 3 and m["kpi"]["bulletins"] == 3
    # le coût se décompose exactement en ses parties
    assert abs(sum(m["decomposition"]["valeurs"]) - m["kpi"]["cout_total"]) < 1
    assert dict(zip(m["par_service"]["labels"], m["par_service"]["cout"]))["Administration"] > 0
    assert j["previsionnel"]["kpi"]["cout_annuel"] == pytest.approx(j["previsionnel"]["kpi"]["cout_mensuel"] * 12)
    assert j["previsionnel"]["kpi"]["salaries_chiffres"] == 3


def test_statistiques_filtre_par_service(client, admin, paie_validee):
    j = client.get("/tableau-de-bord/statistiques", headers=admin, params={"service_id": paie_validee["EXP"]}).json()
    assert j["effectifs"]["kpi"]["effectif"] == 2 and j["masse"]["kpi"]["bulletins"] == 2
    assert j["previsionnel"]["kpi"]["salaries_chiffres"] == 2


def test_statistiques_blocs_selon_les_droits(client, db, admin, paie_validee):
    creer_compte(db, "rh", role="paie", permissions=["voir_salaries"])
    j = client.get("/tableau-de-bord/statistiques", headers=connexion(client, "rh")).json()
    assert j["effectifs"] is not None and j["masse"] is None and j["previsionnel"] is None
    creer_compte(db, "cpt", role="direction", permissions=["voir_rapports"])
    j = client.get("/tableau-de-bord/statistiques", headers=connexion(client, "cpt")).json()
    assert j["effectifs"] is None and j["masse"] is not None
    creer_compte(db, "nul", role="paie", permissions=[])
    assert client.get("/tableau-de-bord/statistiques", headers=connexion(client, "nul")).status_code == 403
    creer_compte(db, "sal", role="salarie")
    assert client.get("/tableau-de-bord/statistiques", headers=connexion(client, "sal")).status_code == 403


# ------------------------------------------------------------------ enfants à charge
def test_enfants_mettent_a_jour_le_compteur(client, admin):
    sid = salarie(client, admin, situation_matrimoniale="marie")
    r = client.post(f"/salaries/{sid}/enfants", headers=admin, json={"nom": "KONE", "prenoms": "Awa", "date_naissance": "2018-05-01", "sexe": "F"})
    assert r.status_code == 201
    client.post(f"/salaries/{sid}/enfants", headers=admin, json={"nom": "KONE", "prenoms": "Moussa", "date_naissance": "2020-05-01", "sexe": "M"})
    j = client.post(f"/salaries/{sid}/enfants", headers=admin, json={"nom": "KONE", "prenoms": "Fanta", "lien": "conjoint"}).json()
    assert j["nombre_enfants"] == 2 and j["parts_suggerees"] == 3.0 and j["parts_actuelles"] == 2.0
    assert client.get(f"/salaries/{sid}", headers=admin).json()["nombre_enfants"] == 2
    premier = j["elements"][0]
    assert client.patch(f"/salaries/{sid}/enfants/{premier['id']}", headers=admin, json={"a_charge": False}).json()["nombre_enfants"] == 1
    assert client.delete(f"/salaries/{sid}/enfants/{premier['id']}", headers=admin).json()["nombre_enfants"] == 1
    assert client.delete(f"/salaries/{sid}/enfants/99999", headers=admin).status_code == 404
    assert client.post(f"/salaries/{sid}/enfants", headers=admin, json={"nom": "X", "date_naissance": "2999-01-01"}).status_code == 422


def test_situation_famille_liste_les_enfants(client, admin):
    sid = salarie(client, admin, matricule="7", situation_matrimoniale="marie")
    client.post(f"/salaries/{sid}/enfants", headers=admin, json={"nom": "KONE", "prenoms": "Awa", "date_naissance": "2018-05-01"})
    r = client.get("/rapports/situation-famille", headers=admin).json()
    assert r["lignes"][0][0] == "000007" and r["lignes"][0][3] == 1 and "Awa" in r["lignes"][0][6]


# ------------------------------------------------------------------ rubriques fixes
def test_rubrique_fixe_ajoutee_a_chaque_bulletin_mensuel(client, db, admin):
    client.post("/rubriques", headers=admin, json={"code": "PRIM", "libelle": "Prime de panier", "type": "GI"})
    sid = salarie(client, admin, matricule="1")
    avant = net(client, admin, paie(client, db, admin, mois=1), "000001")
    r = client.post(f"/salaries/{sid}/rubriques-fixes", headers=admin,
                    json={"code": "prim", "montant": 25000, "date_debut": "2026-02-01", "date_fin": "2026-03-31", "commentaire": "Astreinte"})
    assert r.status_code == 201, r.text
    assert r.json()["code"] == "PRIM" and r.json()["libelle"] == "Prime de panier"
    # janvier : avant le début ; février et mars : la prime ; avril : après la fin
    assert "PRIM" not in lignes_bulletin(client, admin, paie(client, db, admin, mois=1), "000001")
    c2, c3, c4 = (paie(client, db, admin, mois=m) for m in (2, 3, 4))
    assert "PRIM" in lignes_bulletin(client, admin, c2, "000001") and "PRIM" in lignes_bulletin(client, admin, c3, "000001")
    assert "PRIM" not in lignes_bulletin(client, admin, c4, "000001")
    assert D(lignes_bulletin(client, admin, c2, "000001")["PRIM"]["montant"]) == 25000
    assert net(client, admin, c2, "000001") > avant
    # arrêt : désactivée, plus jamais appliquée
    fid = client.get(f"/salaries/{sid}/rubriques-fixes", headers=admin).json()[0]["id"]
    assert client.delete(f"/salaries/{sid}/rubriques-fixes/{fid}", headers=admin).json()["est_actif"] is False
    client.post(f"/campagnes/{c2}/calculer", headers=admin)
    assert "PRIM" not in lignes_bulletin(client, admin, c2, "000001")


def test_rubrique_fixe_validations_et_droits(client, db, admin):
    client.post("/rubriques", headers=admin, json={"code": "PRIM", "libelle": "Prime", "type": "GI"})
    sid = salarie(client, admin)
    assert client.post(f"/salaries/{sid}/rubriques-fixes", headers=admin, json={"code": "ZZZ", "montant": 1000, "date_debut": "2026-01-01"}).status_code == 422
    assert client.post(f"/salaries/{sid}/rubriques-fixes", headers=admin, json={"code": "PRIM", "montant": 1000, "date_debut": "2026-02-01", "date_fin": "2026-01-01"}).status_code == 422
    creer_compte(db, "gp", role="paie", permissions=PERMISSIONS_PAR_DEFAUT["paie"])     # sans « données sensibles »
    assert client.get(f"/salaries/{sid}/rubriques-fixes", headers=connexion(client, "gp")).status_code == 403


# ------------------------------------------------------------------ augmentations en masse
def augmenter(client, h, **plus):
    corps = {"libelle": "Augmentation générale 2026", "mode": "pourcentage", "valeur": 5, "date_effet": "2026-07-01", **plus}
    return client.post("/augmentations", headers=h, json=corps)


def test_apercu_ne_modifie_rien(client, admin):
    sid = salarie(client, admin, salaire_base=200000, sursalaire=50000)
    r = client.post("/augmentations/apercu", headers=admin, json={"libelle": "Test", "mode": "pourcentage", "valeur": 10, "date_effet": "2026-07-01", "cible": "les_deux"})
    a = r.json()
    assert r.status_code == 200 and a["nombre"] == 1 and D(str(a["lignes"][0]["nouveau_salaire"])) == 220000
    assert D(str(a["lignes"][0]["nouveau_sursalaire"])) == 55000 and D(str(a["total_mensuel"])) == 25000 and D(str(a["total_annuel"])) == 300000
    assert len(client.get(f"/salaries/{sid}/salaires", headers=admin).json()) == 1


def test_application_par_lot_et_historique(client, admin):
    ids = [salarie(client, admin, matricule=str(i), salaire_base=b) for i, b in ((1, 200000), (2, 333333))]
    r = augmenter(client, admin, valeur=3, arrondi=100)
    assert r.status_code == 201, r.text
    lot = r.json()
    assert lot["nb_salaries"] == 2
    s1 = client.get(f"/salaries/{ids[0]}/salaires", headers=admin).json()
    s2 = client.get(f"/salaries/{ids[1]}/salaires", headers=admin).json()
    assert s1[0]["montant"] == 206000 and s1[0]["date_effet"] == "2026-07-01" and "Augmentation générale" in s1[0]["motif"]
    assert s2[0]["montant"] == 343300                                   # 333 333 × 1,03 = 343 332,99 -> arrondi à la centaine
    assert D(str(lot["total_mensuel"])) == 6000 + 9967
    # la frise du dossier reprend l'augmentation
    assert any(l["nature"] == "salaire" and l["date"] == "2026-07-01" for l in client.get(f"/salaries/{ids[0]}/historique", headers=admin).json())
    assert len(client.get("/augmentations", headers=admin).json()) == 1


def test_augmentation_filtres_montant_fixe_et_ignores(client, admin):
    client.post("/referentiels", headers=admin, json={"type_ref": "service", "code": "EXP", "libelle": "Exploitation"})
    serv = client.get("/referentiels?type_ref=service", headers=admin).json()[0]["id"]
    a = salarie(client, admin, matricule="1", service_id=serv)
    b = salarie(client, admin, matricule="2")
    r = augmenter(client, admin, mode="montant", valeur=15000, filtres={"service_id": serv})
    assert r.json()["nb_salaries"] == 1
    assert client.get(f"/salaries/{a}/salaires", headers=admin).json()[0]["montant"] == 215000
    assert len(client.get(f"/salaries/{b}/salaires", headers=admin).json()) == 1
    # même date d'effet : le salarié déjà augmenté est écarté, l'autre est pris
    ap = client.post("/augmentations/apercu", headers=admin, json={"libelle": "Bis", "mode": "montant", "valeur": 1000, "date_effet": "2026-07-01"}).json()
    assert ap["nombre"] == 1 and ap["lignes"][0]["matricule"] == "000002" and ap["ignores"][0]["matricule"] == "000001"
    # montant fixe + « les deux » est refusé ; lot vide refusé
    assert augmenter(client, admin, mode="montant", cible="les_deux").status_code == 422
    assert augmenter(client, admin, filtres={"service_id": 99999}).status_code == 422


def test_annulation_du_lot(client, db, admin):
    sid = salarie(client, admin)
    lot = augmenter(client, admin).json()
    assert client.post(f"/augmentations/{lot['id']}/annuler", headers=admin).json()["statut"] == "annule"
    assert len(client.get(f"/salaries/{sid}/salaires", headers=admin).json()) == 1
    assert client.post(f"/augmentations/{lot['id']}/annuler", headers=admin).status_code == 409


def test_annulation_refusee_si_paie_validee(client, db, admin):
    salarie(client, admin)
    lot = augmenter(client, admin, date_effet="2026-03-01").json()
    cid = paie(client, db, admin, mois=3)
    confirmer(db)
    assert client.post(f"/campagnes/{cid}/valider", headers=admin).status_code == 200
    r = client.post(f"/augmentations/{lot['id']}/annuler", headers=admin)
    assert r.status_code == 409 and "déjà validée" in r.json()["detail"]


def test_augmentation_reservee_aux_droits_sensibles(client, db, admin):
    salarie(client, admin)
    creer_compte(db, "gp", role="paie", permissions=PERMISSIONS_PAR_DEFAUT["paie"])
    assert augmenter(client, connexion(client, "gp")).status_code == 403


# ------------------------------------------------------------------ simulation
def test_simulation_egale_le_vrai_bulletin_et_n_ecrit_rien(client, db, admin):
    sid = salarie(client, admin, matricule="1")
    cid = paie(client, db, admin, mois=3)
    vrai = net(client, admin, cid, "000001")
    r = client.post("/simulation/bulletin", headers=admin, json={"annee": 2026, "mois": 3, "salarie_id": sid})
    assert r.status_code == 200, r.text
    assert D(str(r.json()["totaux"]["net_a_payer"])) == vrai and r.json()["cout_employeur"] > r.json()["totaux"]["total_imposable"]
    assert {l["code"] for l in r.json()["lignes"]} >= {"JT", "CNP", "NET"}
    # hypothèse : 10 h sup + prime ponctuelle -> net plus élevé, bulletin réel inchangé
    h = client.post("/simulation/bulletin", headers=admin, json={"annee": 2026, "mois": 3, "salarie_id": sid, "hs1": 10,
                                                                  "rubriques": [{"code": "PRM", "type": "GI", "montant": 50000}]}).json()
    assert D(str(h["totaux"]["net_a_payer"])) > vrai
    assert net(client, admin, cid, "000001") == vrai
    assert client.get(f"/campagnes/{cid}/bulletins", headers=admin).json().__len__() == 1


def test_simulation_manuelle_et_validations(client, db, admin):
    r = client.post("/simulation/bulletin", headers=admin, json={"annee": 2026, "mois": 3, "salaire_categoriel": 300000, "sursalaire": 20000, "parts": 2.5})
    assert r.status_code == 200 and D(str(r.json()["totaux"]["total_imposable"])) >= 320000
    assert client.post("/simulation/bulletin", headers=admin, json={"annee": 2026, "mois": 3}).status_code == 422
    assert client.post("/simulation/bulletin", headers=admin, json={"annee": 2026, "mois": 3, "salarie_id": 999}).status_code == 404
    assert client.post("/simulation/bulletin", headers=admin, json={"annee": 2026, "mois": 13, "salaire_categoriel": 1}).status_code == 422
    creer_compte(db, "gp", role="paie", permissions=PERMISSIONS_PAR_DEFAUT["paie"])
    assert client.post("/simulation/bulletin", headers=connexion(client, "gp"), json={"annee": 2026, "mois": 3, "salaire_categoriel": 1}).status_code == 403


# ------------------------------------------------------------------ journaux
def test_journaux_et_cumuls(client, db, admin):
    sid = salarie(client, admin, matricule="1")
    client.post("/rubriques", headers=admin, json={"code": "PRIM", "libelle": "Prime", "type": "GI"})
    cid = client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 3}).json()["id"]
    client.post(f"/campagnes/{cid}/initialiser", headers=admin)
    client.post(f"/campagnes/{cid}/saisies", headers=admin, json={"salarie_id": sid, "code": "PRIM", "montant": 10000})
    client.post(f"/campagnes/{cid}/calculer", headers=admin)
    j = client.get("/rapports/journal-rubriques?annee=2026&mois=3", headers=admin).json()
    assert len(j["lignes"]) == 1 and j["lignes"][0][3] == "PRIM"
    assert len(client.get("/rapports/journal-presences?annee=2026&mois=3", headers=admin).json()["lignes"]) == 1
    c = client.get("/rapports/bulletins-a-controler?annee=2026&mois=3", headers=admin).json()
    assert len(c["lignes"]) == 1 and c["lignes"][0][1] == "Calculée"
    confirmer(db)
    client.post(f"/campagnes/{cid}/valider", headers=admin)
    cu = client.get("/rapports/cumuls-annuels?annee=2026", headers=admin).json()
    assert cu["lignes"][0][0] == "000001" and cu["lignes"][0][2] == 1
    assert client.get("/rapports/bulletins-a-controler?annee=2026&mois=3", headers=admin).json()["lignes"] == []
    assert client.get("/rapports/liste-personnel", headers=admin).json()["lignes"][0][0] == "000001"
    assert client.get("/rapports/journal-conges?annee=2026", headers=admin).status_code == 200
    assert client.get("/rapports/journal-prets", headers=admin).status_code == 200
    assert client.get("/rapports/cumuls-annuels?annee=2026&format=xlsx", headers=admin).content[:2] == b"PK"


def test_journaux_nominatifs_reserves_aux_droits_sensibles(client, db, admin):
    creer_compte(db, "dir", role="direction", permissions=["voir_rapports"])
    h = connexion(client, "dir")
    for url in ("/rapports/journal-rubriques?annee=2026&mois=3", "/rapports/journal-prets", "/rapports/cumuls-annuels?annee=2026",
                "/rapports/bulletins-a-controler?annee=2026&mois=3"):
        assert client.get(url, headers=h).status_code == 403, url
    assert client.get("/rapports/liste-personnel", headers=h).status_code == 200


# ------------------------------------------------------------------ congés : mode de paiement paramétrable
def regler_param(db, cle, valeur):
    db.execute(text("INSERT INTO valeurs_parametres (parametre_cle, valeur, date_effet, statut, source, cree_par) "
                    "VALUES (:c, :v, DATE '2020-01-01', 'confirme', 'test', 'test') ON CONFLICT (parametre_cle, date_effet) DO UPDATE SET valeur = :v"),
               {"c": cle, "v": str(valeur)})
    db.commit()


def conge_approuve(client, h, sid, debut="2026-03-02", fin="2026-03-07"):
    c = client.post("/conges", headers=h, json={"salarie_id": sid, "debut": debut, "fin": fin}).json()
    assert client.post(f"/conges/{c['id']}/decision", headers=h, json={"decision": "approuver"}).status_code == 200


def test_conges_maintien_du_salaire_par_defaut(client, db, admin):
    sid = salarie(client, admin, matricule="1", date_embauche="2020-01-01")
    conge_approuve(client, admin, sid)
    l = lignes_bulletin(client, admin, paie(client, db, admin, mois=3), "000001")
    assert "ICP" not in l and "CGR" not in l


def test_conges_en_indemnite_remplace_le_salaire_des_jours_pris(client, db, admin):
    sid = salarie(client, admin, matricule="1", date_embauche="2020-01-01", salaire_base=260000)
    conge_approuve(client, admin, sid)                                  # lun 2 -> sam 7 mars 2026 = 6 jours ouvrables
    sans = net(client, admin, paie(client, db, admin, mois=3), "000001")
    regler_param(db, "conges_mode_paiement", "indemnite_conges")
    cid = paie(client, db, admin, mois=3)
    l = lignes_bulletin(client, admin, cid, "000001")
    assert D(l["CGR"]["montant"]) == 60000 and D(l["ICP"]["montant"]) == 60000            # 260 000 ÷ 26 × 6
    assert l["CGR"]["type"] == "RI" and l["ICP"]["type"] == "GI" and D(l["ICP"]["quantite"]) == 6
    assert net(client, admin, cid, "000001") == sans                                      # neutre sans majoration
    regler_param(db, "conges_majoration_indemnite", 10)
    cid = paie(client, db, admin, mois=3)
    assert D(lignes_bulletin(client, admin, cid, "000001")["ICP"]["montant"]) == 66000
    assert net(client, admin, cid, "000001") > sans


def test_conges_indemnite_ignore_les_autres_types_et_les_autres_mois(client, db, admin):
    regler_param(db, "conges_mode_paiement", "indemnite_conges")
    sid = salarie(client, admin, matricule="1", date_embauche="2020-01-01")
    c = client.post("/conges", headers=admin, json={"salarie_id": sid, "type_conge": "maladie", "debut": "2026-03-02", "fin": "2026-03-04"}).json()
    client.post(f"/conges/{c['id']}/decision", headers=admin, json={"decision": "approuver"})
    conge_approuve(client, admin, sid, "2026-04-06", "2026-04-08")
    assert "ICP" not in lignes_bulletin(client, admin, paie(client, db, admin, mois=3), "000001")
    assert "ICP" in lignes_bulletin(client, admin, paie(client, db, admin, mois=4), "000001")


def test_parametre_mode_conges_valide_les_valeurs(client, admin):
    r = client.post("/parametres/conges_mode_paiement/valeurs", headers=admin, json={"valeur": "n_importe_quoi", "date_effet": "2026-01-01"})
    assert r.status_code == 422
    r = client.post("/parametres/conges_mode_paiement/valeurs", headers=admin, json={"valeur": "indemnite_conges", "date_effet": "2026-01-01", "source": "Note de la direction"})
    assert r.status_code == 201


def test_acces_espace_salarie_detecte(client, db):
    creer_compte(db)
    h = connexion(client)
    sid = client.post("/salaries", headers=h, json={"nom": "ACCES", "matricule": "55"}).json()["id"]
    assert client.get(f"/salaries/{sid}/acces", headers=h).json()["existe"] is False
    assert client.post(f"/salaries/{sid}/creer-compte", headers=h).status_code == 201
    j = client.get(f"/salaries/{sid}/acces", headers=h).json()
    assert j["existe"] is True and j["est_actif"] is True and j["utilisateur_id"]
