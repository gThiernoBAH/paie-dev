import re
import secrets

import bcrypt

from .settings import settings

# Hash factice pour égaliser le temps de réponse quand l'identifiant n'existe pas
# (sinon la durée de la réponse révèle quels matricules existent).
_HASH_FACTICE = bcrypt.hashpw(b"mot-de-passe-factice", bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def verifier_faux_mot_de_passe(plain_password: str) -> None:
    """Dépense le même temps de calcul qu'une vraie vérification."""
    verify_password(plain_password, _HASH_FACTICE)


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def erreurs_mot_de_passe(mot_de_passe: str, identifiant: str = "") -> list[str]:
    """Liste des règles non respectées (vide = mot de passe acceptable)."""
    erreurs = []
    if len(mot_de_passe) < settings.PASSWORD_MIN_LENGTH:
        erreurs.append(f"au moins {settings.PASSWORD_MIN_LENGTH} caractères")
    if not re.search(r"[A-Za-z]", mot_de_passe):
        erreurs.append("au moins une lettre")
    if not re.search(r"\d", mot_de_passe):
        erreurs.append("au moins un chiffre")
    if identifiant and mot_de_passe.lower() == identifiant.lower():
        erreurs.append("différent de l'identifiant")
    return erreurs


def generer_mot_de_passe_temporaire() -> str:
    """Mot de passe temporaire lisible (sans caractères ambigus), conforme à la politique."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    while True:
        mdp = "".join(secrets.choice(alphabet) for _ in range(max(12, settings.PASSWORD_MIN_LENGTH)))
        if not erreurs_mot_de_passe(mdp):
            return mdp
