"""Prêts : règlement manuel d'une échéance et clôture anticipée (départ, démission, décès)."""
import pytest

from tests.conftest import connexion, creer_compte
from tests.test_conges_prets_soldes import nouveau, tout_confirmer


@pytest.fixture
def admin(client, db):
    creer_compte(db)
    return connexion(client)


def pret_de(client, h, sid, montant=90000, n=3, annee=2026, mois=2):
    r = client.post("/prets", headers=h, json={"salarie_id": sid, "libelle": "Prêt test", "montant": montant,
                                               "nombre_echeances": n, "annee_debut": annee, "mois_debut": mois})
    assert r.status_code == 201, r.text
    return r.json()


def test_reglement_manuel_retire_l_echeance_de_la_paie(client, admin):
    sid = nouveau(client, admin)
    p = pret_de(client, admin, sid)
    e0 = p["echeances"][0]["id"]
    r = client.post(f"/prets/{p['id']}/echeances/{e0}/regler", headers=admin,
                    json={"date_reglement": "2026-02-10", "mode_reglement": "especes", "commentaire": "Remis à la caisse"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["echeances"][0]["statut"] == "reglee" and j["echeances"][0]["mode_reglement"] == "especes"
    assert float(j["reste"]) == 60000 and float(j["regle"]) == 30000 and j["echeances_reglees"] == 1
    # février : l'échéance déjà réglée n'est plus retenue ; mars l'est
    c = client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 2}).json()
    client.post(f"/campagnes/{c['id']}/initialiser", headers=admin)
    client.post(f"/campagnes/{c['id']}/calculer", headers=admin)
    assert client.get(f"/campagnes/{c['id']}/saisies", headers=admin).json() == []      # février réglé ; mars n'est pas encore due
    # double règlement refusé
    assert client.post(f"/prets/{p['id']}/echeances/{e0}/regler", headers=admin,
                       json={"date_reglement": "2026-02-10"}).status_code == 409


def test_reglement_d_une_echeance_deja_dans_une_campagne_regenere_la_retenue(client, admin):
    sid = nouveau(client, admin)
    p = pret_de(client, admin, sid, montant=60000, n=2, mois=2)
    c = client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 2}).json()
    client.post(f"/campagnes/{c['id']}/initialiser", headers=admin)
    client.post(f"/campagnes/{c['id']}/calculer", headers=admin)
    assert len(client.get(f"/campagnes/{c['id']}/saisies", headers=admin).json()) == 1
    r = client.post(f"/prets/{p['id']}/echeances/{p['echeances'][0]['id']}/regler", headers=admin,
                    json={"date_reglement": "2026-02-12", "mode_reglement": "virement"})
    assert r.status_code == 200
    assert r.json()["campagnes_a_recalculer"] == [c["libelle"]]                 # bulletin déjà calculé : à recalculer
    assert client.get(f"/campagnes/{c['id']}/saisies", headers=admin).json() == []


def test_annuler_un_reglement_manuel(client, admin):
    sid = nouveau(client, admin)
    p = pret_de(client, admin, sid, montant=20000, n=2)
    e0 = p["echeances"][0]["id"]
    client.post(f"/prets/{p['id']}/echeances/{e0}/regler", headers=admin, json={"date_reglement": "2026-02-10"})
    r = client.post(f"/prets/{p['id']}/echeances/{e0}/rouvrir", headers=admin)
    assert r.status_code == 200 and r.json()["echeances"][0]["statut"] == "prevue" and r.json()["echeances"][0]["date_reglement"] is None
    # une échéance « prévue » ne se rouvre pas
    assert client.post(f"/prets/{p['id']}/echeances/{e0}/rouvrir", headers=admin).status_code == 409


def test_prelevee_sur_paie_ne_se_rouvre_pas(client, db, admin):
    sid = nouveau(client, admin)
    p = pret_de(client, admin, sid, montant=20000, n=2, mois=1)
    c = client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 1}).json()
    client.post(f"/campagnes/{c['id']}/initialiser", headers=admin)
    client.post(f"/campagnes/{c['id']}/calculer", headers=admin)
    tout_confirmer(db)
    assert client.post(f"/campagnes/{c['id']}/valider", headers=admin).status_code == 200
    j = client.get(f"/prets/{p['id']}", headers=admin).json()
    assert j["echeances"][0]["statut"] == "prelevee" and j["echeances"][0]["campagne"] == c["libelle"]
    assert client.post(f"/prets/{p['id']}/echeances/{j['echeances'][0]['id']}/rouvrir", headers=admin).status_code == 409
    assert client.post(f"/prets/{p['id']}/echeances/{j['echeances'][0]['id']}/regler", headers=admin,
                       json={"date_reglement": "2026-02-10"}).status_code == 409


def test_pret_solde_quand_tout_est_regle(client, admin):
    sid = nouveau(client, admin)
    p = pret_de(client, admin, sid, montant=20000, n=2)
    for e in p["echeances"]:
        r = client.post(f"/prets/{p['id']}/echeances/{e['id']}/regler", headers=admin, json={"date_reglement": "2026-03-01", "mode_reglement": "cheque"})
        assert r.status_code == 200
    assert r.json()["statut"] == "solde" and float(r.json()["reste"]) == 0
    # un prêt soldé n'accepte plus de règlement
    assert client.post(f"/prets/{p['id']}/echeances/{p['echeances'][0]['id']}/regler", headers=admin,
                       json={"date_reglement": "2026-03-01"}).status_code == 409


@pytest.mark.parametrize("motif", ["depart", "demission", "deces"])
def test_cloture_passe_en_perte(client, admin, motif):
    sid = nouveau(client, admin)
    p = pret_de(client, admin, sid, montant=90000, n=3)
    client.post(f"/prets/{p['id']}/echeances/{p['echeances'][0]['id']}/regler", headers=admin, json={"date_reglement": "2026-02-10"})
    r = client.post(f"/prets/{p['id']}/cloturer", headers=admin,
                    json={"motif": motif, "issue": "abandon", "date_cloture": "2026-03-15", "commentaire": "Sans nouvelles"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["statut"] == "cloture" and j["motif_cloture"] == motif and j["issue_cloture"] == "abandon"
    assert float(j["reste"]) == 0 and float(j["abandonne"]) == 60000 and float(j["regle"]) == 30000
    assert [e["statut"] for e in j["echeances"]] == ["reglee", "abandonnee", "abandonnee"]
    # clôturé : plus de nouvelle clôture, plus d'annulation
    assert client.post(f"/prets/{p['id']}/cloturer", headers=admin,
                       json={"motif": motif, "issue": "abandon", "date_cloture": "2026-03-16"}).status_code == 409
    assert client.post(f"/prets/{p['id']}/annuler", headers=admin).status_code == 409


def test_cloture_regularisee_hors_paie(client, admin):
    sid = nouveau(client, admin)
    p = pret_de(client, admin, sid, montant=40000, n=2)
    r = client.post(f"/prets/{p['id']}/cloturer", headers=admin,
                    json={"motif": "deces", "issue": "regularise", "date_cloture": "2026-03-15", "commentaire": "Versé par la famille"})
    j = r.json()
    assert r.status_code == 200 and j["statut"] == "cloture" and float(j["regle"]) == 40000 and float(j["abandonne"]) == 0
    assert all(e["statut"] == "reglee" and e["date_reglement"] == "2026-03-15" for e in j["echeances"])


def test_cloture_retire_les_echeances_de_la_campagne_en_cours(client, admin):
    sid = nouveau(client, admin)
    p = pret_de(client, admin, sid, montant=60000, n=2, mois=2)
    c = client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 2}).json()
    client.post(f"/campagnes/{c['id']}/initialiser", headers=admin)
    client.post(f"/campagnes/{c['id']}/calculer", headers=admin)
    assert len(client.get(f"/campagnes/{c['id']}/saisies", headers=admin).json()) == 1
    r = client.post(f"/prets/{p['id']}/cloturer", headers=admin, json={"motif": "demission", "issue": "abandon", "date_cloture": "2026-02-20"})
    assert r.status_code == 200 and r.json()["campagnes_a_recalculer"] == [c["libelle"]]
    assert client.get(f"/campagnes/{c['id']}/saisies", headers=admin).json() == []
    # recalcul : aucune retenue ne revient
    client.post(f"/campagnes/{c['id']}/calculer", headers=admin)
    assert client.get(f"/campagnes/{c['id']}/saisies", headers=admin).json() == []


def test_cloture_validations_et_droits(client, db, admin):
    sid = nouveau(client, admin)
    p = pret_de(client, admin, sid, montant=20000, n=2)
    base = {"issue": "abandon", "date_cloture": "2026-03-15"}
    assert client.post(f"/prets/{p['id']}/cloturer", headers=admin, json={**base, "motif": "inconnu"}).status_code == 422
    assert client.post(f"/prets/{p['id']}/cloturer", headers=admin, json={"motif": "deces", "issue": "gratuit", "date_cloture": "2026-03-15"}).status_code == 422
    assert client.post("/prets/9999/cloturer", headers=admin, json={**base, "motif": "deces"}).status_code == 404
    creer_compte(db, "lecteur", "direction")
    h = connexion(client, "lecteur")
    assert client.post(f"/prets/{p['id']}/cloturer", headers=h, json={**base, "motif": "deces"}).status_code == 403
    assert client.post(f"/prets/{p['id']}/echeances/{p['echeances'][0]['id']}/regler", headers=h, json={"date_reglement": "2026-03-01"}).status_code == 403


def test_cloture_et_reglement_sont_audites(client, admin):
    sid = nouveau(client, admin)
    p = pret_de(client, admin, sid, montant=20000, n=2)
    client.post(f"/prets/{p['id']}/echeances/{p['echeances'][0]['id']}/regler", headers=admin, json={"date_reglement": "2026-03-01"})
    client.post(f"/prets/{p['id']}/cloturer", headers=admin, json={"motif": "deces", "issue": "abandon", "date_cloture": "2026-03-15"})
    actions = {a["action"] for a in client.get("/admin/audit", headers=admin, params={"taille": 50}).json()["elements"]}
    assert {"pret_echeance_reglee", "pret_cloture"} <= actions
