"""Jeu de données de DÉMONSTRATION pour tester l'application (jamais en production).

    ADMIN_PASSWORD='...' .venv/bin/python -m scripts.demo_data [--identifiant admin] [--confirmer-parametres]

Crée : des référentiels, 12 salariés fictifs (dont le cas de référence matricule 000054 = bulletin de janvier 2026
dont le net doit être 205 014 FCFA), des journaliers avec leurs pointages de janvier 2026, un prêt, une demande de congé et
trois comptes de test. Les écritures passent par l'API (mêmes contrôles que l'application).
Refuse de tourner sur une base dont le nom ne contient pas « dev » ou « demo », ou qui contient déjà des salariés.
"""
import argparse
import os
import sys
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.core.settings import settings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--identifiant", default="admin")
    ap.add_argument("--confirmer-parametres", action="store_true", help="marque tous les paramètres « à confirmer » comme confirmés (démo seulement)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    nom_base = settings.DATABASE_URL.rsplit("/", 1)[-1]
    if not args.force and not any(m in nom_base for m in ("dev", "demo")):
        print(f"Refusé : la base « {nom_base} » n'est pas une base de développement ou de démonstration.")
        return 1
    mot_de_passe = os.environ.get("ADMIN_PASSWORD")
    if not mot_de_passe:
        print("Renseigner ADMIN_PASSWORD (mot de passe du compte administrateur).")
        return 1

    from app.main import app
    c = TestClient(app)
    r = c.post("/auth/login", json={"identifiant": args.identifiant, "password": mot_de_passe})
    if r.status_code != 200:
        print("Connexion impossible :", r.text)
        return 1
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def ok(rep, ce_quon_fait):
        if rep.status_code >= 300:
            print(f"ECHEC ({ce_quon_fait}) : {rep.status_code} {rep.text}")
            sys.exit(1)
        return rep.json()

    if ok(c.get("/salaries?taille=1", headers=h), "lecture")["total"] > 0:
        print("Refusé : des salariés existent déjà.")
        return 1

    # --- référentiels
    ids = {}
    for type_ref, code, lib in [
        ("service", "EXP", "Exploitation"), ("service", "ADM", "Administration"), ("service", "MAI", "Maintenance"), ("service", "COM", "Commercial"),
        ("emploi", "OPE", "Opérateur"), ("emploi", "TEC", "Technicien"), ("emploi", "COMP", "Comptable"), ("emploi", "CHF", "Chef d'atelier"), ("emploi", "MAN", "Manœuvre"),
        ("categorie", "C3", "Catégorie 3"), ("categorie", "C5", "Catégorie 5"), ("categorie", "C7", "Catégorie 7"), ("categorie", "M1", "Manœuvre"),
        ("site", "ABJ", "Abidjan – Siège"), ("site", "YOP", "Yopougon – Usine"),
    ]:
        ids[(type_ref, code)] = ok(c.post("/referentiels", headers=h, json={"type_ref": type_ref, "code": code, "libelle": lib}), f"référentiel {code}")["id"]
    banques = ok(c.get("/referentiels?type_ref=banque", headers=h), "banques")
    banque = banques[0]["id"] if banques else None
    contrats = {x["code"]: x["id"] for x in ok(c.get("/referentiels?type_ref=type_contrat", headers=h), "contrats")}
    cdi = next(iter(contrats.values()), None)

    def salarie(matricule, nom, prenoms, **plus):
        corps = {"matricule": matricule, "nom": nom, "prenoms": prenoms, "sexe": "M", "mode_paiement": "virement", "banque_id": banque,
                 "type_contrat_id": cdi, "email": f"{prenoms.split()[0].lower()}.{nom.lower()}@exemple.ci",
                 "site_id": ids[("site", "ABJ")], "rib": f"CI0080100{matricule}0123456789", "numero_cnps": f"1{matricule}2026", **plus}
        corps = {k: v for k, v in corps.items() if v is not None}
        return ok(c.post("/salaries", headers=h, json=corps), f"salarié {matricule}")["id"]

    S = lambda t, k: ids[(t, k)]
    ref = salarie("000054", "TRAORE", "Mamadou", date_naissance="1964-05-12", date_embauche="1988-01-04", situation_matrimoniale="marie",
                  nombre_enfants=8, nombre_parts=5, nombre_personnes_cmu=4, indemnite_transport=38102, salaire_base=135540, sursalaire=69899,
                  service_id=S("service", "EXP"), emploi_id=S("emploi", "CHF"), categorie_id=S("categorie", "C7"))
    mensuels = [
        ("000055", "KONE", "Aminata", "F", "1990-03-08", "2015-06-01", "celibataire", 0, 1, 1, 180000, 20000, "ADM", "COMP", "C5"),
        ("000056", "YAO", "Koffi Jean", "M", "1985-11-21", "2012-02-15", "marie", 3, 3.5, 5, 250000, 45000, "EXP", "TEC", "C5"),
        ("000057", "OUATTARA", "Salif", "M", "1992-07-30", "2019-09-02", "celibataire", 0, 1, 1, 140000, 0, "MAI", "OPE", "C3"),
        ("000058", "N'GUESSAN", "Adjoua", "F", "1988-01-17", "2017-04-10", "marie", 2, 2.5, 4, 210000, 35000, "COM", "COMP", "C5"),
        ("000059", "BAMBA", "Issouf", "M", "1979-09-05", "2005-08-22", "marie", 4, 4, 6, 320000, 80000, "EXP", "CHF", "C7"),
        ("000060", "DIABATE", "Fatou", "F", "1995-12-02", "2023-03-01", "celibataire", 1, 1.5, 2, 120000, 0, "ADM", "OPE", "C3"),
        ("000061", "KOUAME", "Serge", "M", "1983-04-14", "2010-10-04", "marie", 2, 2.5, 4, 195000, 25000, "MAI", "TEC", "C5"),
    ]
    ids_m = {}
    for mat, nom, pre, sexe, nais, emb, sit, enf, parts, cmu, base, sur, serv, emp, cat in mensuels:
        ids_m[mat] = salarie(mat, nom, pre, sexe=sexe, date_naissance=nais, date_embauche=emb, situation_matrimoniale=sit, nombre_enfants=enf,
                             nombre_parts=parts, nombre_personnes_cmu=cmu, salaire_base=base, sursalaire=sur,
                             service_id=S("service", serv), emploi_id=S("emploi", emp), categorie_id=S("categorie", cat))
    journaliers = []
    for i, (nom, pre, mode) in enumerate([("SANOGO", "Lassina", "virement"), ("TIA", "Boris", "especes"), ("COULIBALY", "Mariam", "virement"), ("DOSSO", "Ibrahim", "especes")]):
        mat = f"0001{i + 1:02d}"
        sid = salarie(mat, nom, pre, type_remuneration="journalier", mode_paiement=mode, date_naissance=f"199{i}-0{i + 2}-1{i}", date_embauche="2025-11-03",
                      salaire_base=75000, service_id=S("service", "EXP"), emploi_id=S("emploi", "MAN"), categorie_id=S("categorie", "M1"),
                      eligible_heures_sup=True, rib=None if mode == "especes" else f"CI0080100{mat}0123456789")
        journaliers.append(sid)

    # --- pointages : journaliers, janvier 2026 (lundi-vendredi 08:00-17:00 ; samedi 08:00-13:00 ; jours variables)
    import_lignes = ["matricule;date;entree;sortie"]
    for i, mat in enumerate(f"0001{k + 1:02d}" for k in range(4)):
        jour = date(2026, 1, 5)
        while jour <= date(2026, 1, 31):
            if jour.weekday() < 5 and (jour.day + i) % 6 != 0:
                import_lignes.append(f"{mat};{jour.isoformat()};08:00;{'18:00' if jour.weekday() == 2 else '17:00'}")
            elif jour.weekday() == 5 and i % 2 == 0:
                import_lignes.append(f"{mat};{jour.isoformat()};08:00;13:00")
            jour += timedelta(days=1)
    imp = ok(c.post("/pointages/import", headers=h, json={"nom_fichier": "demo_janvier_2026.csv", "contenu": "\n".join(import_lignes)}), "import pointages")

    # --- un prêt et une demande de congé
    ok(c.post("/prets", headers=h, json={"salarie_id": ids_m["000056"], "libelle": "Prêt scolarité", "montant": 120000, "nombre_echeances": 6,
                                         "annee_debut": 2026, "mois_debut": 2}), "prêt")
    ok(c.post("/conges", headers=h, json={"salarie_id": ids_m["000055"], "type_conge": "annuel", "debut": "2026-04-06", "fin": "2026-04-18"}), "congé")

    # --- campagnes de janvier 2026 préparées (à calculer par le testeur)
    for code, lib, typ in (("PLA", "Prime exceptionnelle (non imposable)", "GN"), ("PLT", "Prime de transport complémentaire", "GN"), ("C08", "Retenue diverse", "RN")):
        ok(c.post("/rubriques", headers=h, json={"code": code, "libelle": lib, "type": typ}), f"rubrique {code}")
    cm = ok(c.post("/campagnes", headers=h, json={"type_campagne": "mensuelle", "annee": 2026, "mois": 1}), "campagne mensuelle")["id"]
    ok(c.post(f"/campagnes/{cm}/initialiser", headers=h), "initialiser mensuelle")
    ok(c.put(f"/campagnes/{cm}/presences/{ref}", headers=h, json={"jours_absence_ja": 3, "heures_absence": 4, "hs1": 3}), "présences 000054")
    for code, montant in (("SAL", "5625.18"), ("PLA", 3029), ("PLT", 1500), ("AS1", 8600), ("C08", 25000)):
        ok(c.post(f"/campagnes/{cm}/saisies", headers=h, json={"salarie_id": ref, "code": code, "montant": montant}), f"saisie {code}")
    for debut, fin in (("2026-01-01", "2026-01-15"), ("2026-01-16", "2026-01-31")):
        cj = ok(c.post("/campagnes", headers=h, json={"type_campagne": "journaliere", "annee": 2026, "mois": 1, "debut": debut, "fin": fin}), "campagne journalière")["id"]
        ok(c.post(f"/campagnes/{cj}/initialiser", headers=h), "initialiser journalière")

    # --- comptes de test
    comptes = []
    for ident, nom, role in (("gestion", "Gestionnaire", "paie"), ("direction", "Direction", "direction")):
        d = ok(c.post("/admin/utilisateurs", headers=h, json={"identifiant": ident, "nom": nom, "role": role}), f"compte {ident}")
        comptes.append((ident, role, d["mot_de_passe_temporaire"]))
    d = ok(c.post(f"/salaries/{ref}/creer-compte", headers=h), "compte salarié")
    comptes.append(("000054", "salarie (TRAORE Mamadou)", d["mot_de_passe_temporaire"]))

    if args.confirmer_parametres:
        from sqlalchemy import text
        from app.core.database import SessionLocal
        with SessionLocal() as db:
            db.execute(text("UPDATE valeurs_parametres SET statut = 'confirme', source = COALESCE(source, '') || ' – confirmé pour la démo'"))
            db.commit()

    print(f"OK : 12 salariés, {imp.get('jours_importes', '?')} jours de pointage importés, 1 prêt, 1 demande de congé.")
    print("Campagnes de janvier 2026 préparées (mensuelle + 2 quinzaines de journaliers) : il reste à les calculer.")
    print("Comptes de test (mot de passe temporaire à changer à la première connexion) :")
    for ident, role, mdp in comptes:
        print(f"  {ident:<10} {role:<28} {mdp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
