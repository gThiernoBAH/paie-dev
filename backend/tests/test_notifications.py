from io import BytesIO

import pytest
from pypdf import PdfReader
from sqlalchemy import text

from app.services import messagerie
from tests.conftest import connexion, creer_compte


@pytest.fixture
def admin(client, db):
    creer_compte(db)
    return connexion(client)


@pytest.fixture
def boite(monkeypatch):
    """Remplace l'envoi réseau : collecte les messages, ou échoue si `boite.panne` est vrai."""
    class Boite:
        messages: list = []
        panne = False
    b = Boite()
    b.messages = []

    def faux(cfg, message):
        if b.panne:
            raise ConnectionRefusedError("serveur SMTP injoignable")
        b.messages.append(message)
    monkeypatch.setattr(messagerie, "_smtp_envoyer", faux)
    return b


def regler(db, **valeurs):
    for cle, v in valeurs.items():
        db.execute(text("UPDATE valeurs_parametres SET valeur = :v WHERE parametre_cle = :c"), {"v": v, "c": cle})
    db.commit()


def salarie(client, h, matricule, **plus):
    base = {"nom": f"NOM{matricule}", "prenoms": "Awa", "matricule": matricule, "date_embauche": "2020-01-01", "salaire_base": 250000,
            "mode_paiement": "virement", "rib": "CI0080101234567890123456", "email": f"s{matricule}@exemple.ci", "date_naissance": "1985-07-14"}
    r = client.post("/salaries", headers=h, json={**base, **plus})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def campagne_validee(client, db, h):
    cid = client.post("/campagnes", headers=h, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 3}).json()["id"]
    client.post(f"/campagnes/{cid}/initialiser", headers=h)
    client.post(f"/campagnes/{cid}/calculer", headers=h)
    db.execute(text("UPDATE valeurs_parametres SET statut = 'confirme'"))
    db.commit()
    assert client.post(f"/campagnes/{cid}/valider", headers=h).status_code == 200
    return cid


def test_desactive_par_defaut_rien_ne_part(client, db, admin, boite):
    salarie(client, admin, "1")
    cid = campagne_validee(client, db, admin)
    r = client.post(f"/campagnes/{cid}/envoyer-bulletins", headers=admin, json={})
    assert r.status_code == 202 and r.json()["en_attente"] == 1
    notifs = client.get(f"/notifications?campagne_id={cid}", headers=admin).json()
    assert notifs[0]["statut"] == "desactive" and boite.messages == []
    assert client.get(f"/campagnes/{cid}/bulletins", headers=admin).json()[0]["envoye_le"] is None


def test_envoi_du_bulletin_pdf_protege_par_la_date_de_naissance(client, db, admin, boite):
    salarie(client, admin, "1")
    regler(db, email_actif="true")
    cid = campagne_validee(client, db, admin)
    client.post(f"/campagnes/{cid}/envoyer-bulletins", headers=admin, json={})
    assert len(boite.messages) == 1
    m = boite.messages[0]
    assert m["To"] == "s1@exemple.ci" and "mars 2026" in m["Subject"] and "Bonjour Awa" in m.get_body().get_content()
    pj = next(m.iter_attachments())
    lecteur = PdfReader(BytesIO(pj.get_content()))
    assert lecteur.is_encrypted
    assert lecteur.decrypt("14071985") > 0
    assert "NET" in lecteur.pages[0].extract_text()
    assert client.get(f"/campagnes/{cid}/bulletins", headers=admin).json()[0]["envoye_le"] is not None
    assert client.get(f"/campagnes/{cid}/envois", headers=admin).json() == {"envoye": 1}
    # un second envoi ne renvoie pas ce qui est déjà parti, sauf demande explicite
    assert client.post(f"/campagnes/{cid}/envoyer-bulletins", headers=admin, json={}).json()["deja_envoyes"] == 1
    assert len(boite.messages) == 1
    client.post(f"/campagnes/{cid}/envoyer-bulletins", headers=admin, json={"renvoyer": True})
    assert len(boite.messages) == 2


def test_pdf_non_protege_si_parametre_desactive(client, db, admin, boite):
    salarie(client, admin, "1", date_naissance=None)
    regler(db, email_actif="true", email_pdf_protege="false")
    cid = campagne_validee(client, db, admin)
    client.post(f"/campagnes/{cid}/envoyer-bulletins", headers=admin, json={})
    assert not PdfReader(BytesIO(next(boite.messages[0].iter_attachments()).get_content())).is_encrypted


def test_salaries_sans_email_ou_sans_date_de_naissance_ignores(client, db, admin, boite):
    salarie(client, admin, "1", email=None)
    salarie(client, admin, "2", date_naissance=None)
    salarie(client, admin, "3")
    regler(db, email_actif="true")
    cid = campagne_validee(client, db, admin)
    r = client.post(f"/campagnes/{cid}/envoyer-bulletins", headers=admin, json={}).json()
    assert r["ignores"] == 2 and r["en_attente"] == 1 and len(boite.messages) == 1
    motifs = {n["erreur"] for n in client.get(f"/notifications?statut=ignore", headers=admin).json()}
    assert any("e-mail" in m for m in motifs) and any("naissance" in m for m in motifs)


def test_echec_smtp_puis_relance(client, db, admin, boite):
    salarie(client, admin, "1")
    regler(db, email_actif="true")
    cid = campagne_validee(client, db, admin)
    boite.panne = True
    client.post(f"/campagnes/{cid}/envoyer-bulletins", headers=admin, json={})
    n = client.get("/notifications?statut=echec", headers=admin).json()
    assert len(n) == 1 and "ConnectionRefusedError" in n[0]["erreur"] and n[0]["tentatives"] == 1
    boite.panne = False
    assert client.post(f"/campagnes/{cid}/relancer-envois", headers=admin).json() == {"relances": 1}
    assert client.get(f"/campagnes/{cid}/envois", headers=admin).json() == {"envoye": 1} and len(boite.messages) == 1


def test_envoi_refuse_avant_validation(client, db, admin, boite):
    salarie(client, admin, "1")
    cid = client.post("/campagnes", headers=admin, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 6}).json()["id"]
    assert client.post(f"/campagnes/{cid}/envoyer-bulletins", headers=admin, json={}).status_code == 409


def test_alerte_au_lancement_du_virement(client, db, admin, boite):
    salarie(client, admin, "1")
    regler(db, email_actif="true", email_alerte_virement_destinataires="daf@exemple.ci, dg@exemple.ci")
    cid = campagne_validee(client, db, admin)
    lot = client.post(f"/campagnes/{cid}/virements", headers=admin, json={}).json()
    assert boite.messages == []                                  # la préparation n'alerte pas
    assert client.post(f"/virements/{lot['id']}/lancer", headers=admin).json()["statut"] == "lance"
    assert len(boite.messages) == 1
    m = boite.messages[0]
    assert "daf@exemple.ci" in m["To"] and "dg@exemple.ci" in m["To"] and "Virement de paie lancé" in m["Subject"]
    assert "admin" in m.get_content()


def test_une_panne_d_alerte_ne_bloque_pas_le_virement(client, db, admin, boite):
    salarie(client, admin, "1")
    regler(db, email_actif="true", email_alerte_virement_destinataires="daf@exemple.ci")
    cid = campagne_validee(client, db, admin)
    lot = client.post(f"/campagnes/{cid}/virements", headers=admin, json={}).json()
    boite.panne = True
    assert client.post(f"/virements/{lot['id']}/lancer", headers=admin).json()["statut"] == "lance"
    assert client.get("/notifications?statut=echec", headers=admin).json()[0]["type"] == "alerte_virement"


def test_alerte_enregistree_meme_si_email_desactive(client, db, admin, boite):
    salarie(client, admin, "1")
    regler(db, email_alerte_virement_destinataires="daf@exemple.ci")
    cid = campagne_validee(client, db, admin)
    lot = client.post(f"/campagnes/{cid}/virements", headers=admin, json={}).json()
    client.post(f"/virements/{lot['id']}/lancer", headers=admin)
    assert client.get("/notifications", headers=admin).json()[0]["statut"] == "desactive" and boite.messages == []


def test_email_de_test_et_droits(client, db, admin, boite):
    regler(db, email_actif="true")
    assert client.post("/email/test", headers=admin, json={"destinataire": "moi@exemple.ci"}).json()["statut"] == "envoye"
    assert client.post("/email/test", headers=admin, json={"destinataire": "pas-une-adresse"}).status_code == 422
    creer_compte(db, "gest", role="paie", permissions=["lancer_paie"])
    h = connexion(client, "gest")
    assert client.post("/email/test", headers=h, json={"destinataire": "moi@exemple.ci"}).status_code == 403
    assert client.post("/campagnes/1/envoyer-bulletins", headers=h, json={}).status_code == 403
