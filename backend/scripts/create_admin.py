#!/usr/bin/env python3
"""
create_admin.py -- Crée le premier compte administrateur (ou réinitialise son mot de passe).

Le mot de passe n'est jamais écrit dans un fichier : il est saisi au clavier (masqué), ou lu dans
la variable d'environnement ADMIN_PASSWORD pour un usage non interactif.

Usage (depuis backend/) :
    python3 -m scripts.create_admin
    python3 -m scripts.create_admin --identifiant admin --nom "Administrateur"
    python3 -m scripts.create_admin --reset-password     # compte existant : nouveau mot de passe
"""
import argparse
import getpass
import os
import sys

from app.core import auth
from app.core.database import SessionLocal
from app.core.models import Utilisateur
from app.core.permissions import PERMISSION_REGISTRY
from app.services import audit


def _lire_mot_de_passe(identifiant: str) -> str:
    depuis_env = os.environ.get("ADMIN_PASSWORD")
    if depuis_env:
        mdp = depuis_env
    else:
        mdp = getpass.getpass("Mot de passe : ")
        if mdp != getpass.getpass("Confirmer le mot de passe : "):
            sys.exit("Les deux saisies diffèrent. Abandon.")
    erreurs = auth.erreurs_mot_de_passe(mdp, identifiant)
    if erreurs:
        sys.exit("Mot de passe refusé : " + ", ".join(erreurs) + ".")
    return mdp


def main() -> None:
    p = argparse.ArgumentParser(description="Crée le compte administrateur initial.")
    p.add_argument("--identifiant", default="admin")
    p.add_argument("--nom", default="Administrateur")
    p.add_argument("--email", default=None)
    p.add_argument("--reset-password", action="store_true", help="Compte existant : change son mot de passe.")
    args = p.parse_args()

    db = SessionLocal()
    try:
        existant = db.query(Utilisateur).filter(Utilisateur.identifiant == args.identifiant).first()
        if existant and not args.reset_password:
            sys.exit(f"Le compte '{args.identifiant}' existe déjà. Utilisez --reset-password pour changer son mot de passe.")

        mot_de_passe = _lire_mot_de_passe(args.identifiant)
        hash_ = auth.get_password_hash(mot_de_passe)

        if existant:
            existant.mot_de_passe_hash = hash_
            existant.est_actif = True
            existant.doit_changer_mot_de_passe = False
            audit.enregistrer(db, "mot_de_passe_reinitialise_console", acteur_identifiant=existant.identifiant,
                              cible_type="utilisateur", cible_id=existant.id)
            db.commit()
            print(f"Mot de passe du compte '{args.identifiant}' mis à jour (ses sessions ouvertes sont invalidées).")
            return

        admin = Utilisateur(
            identifiant=args.identifiant, nom=args.nom, email=(args.email or None) and args.email.lower(),
            role="admin", mot_de_passe_hash=hash_, est_actif=True, doit_changer_mot_de_passe=False,
        )
        db.add(admin)
        db.flush()
        audit.enregistrer(db, "utilisateur_cree_console", acteur_identifiant=args.identifiant,
                          cible_type="utilisateur", cible_id=admin.id, detail={"role": "admin"})
        db.commit()
        print(f"Compte administrateur '{args.identifiant}' créé ({len(PERMISSION_REGISTRY)} permissions implicites).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
