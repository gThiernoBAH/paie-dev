"""Chiffrement des champs sensibles stockés en base (RIB, numéro CNPS, pièce d'identité...).

Fernet (AES-128-CBC + HMAC-SHA256) avec la clé ENCRYPTION_KEY. Une valeur chiffrée commence
par "enc1:" ; une valeur vide reste vide. Les modules métier (lot 2, salariés) s'en servent pour
leurs colonnes sensibles ; aucune donnée sensible n'est stockée en clair.
"""
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from .settings import settings

_PREFIXE = "enc1:"
_fernet = Fernet(settings.ENCRYPTION_KEY.encode("ascii"))


def chiffrer(valeur: Optional[str]) -> Optional[str]:
    if valeur is None or valeur == "":
        return valeur
    return _PREFIXE + _fernet.encrypt(valeur.encode("utf-8")).decode("ascii")


def dechiffrer(valeur: Optional[str]) -> Optional[str]:
    if valeur is None or valeur == "":
        return valeur
    if not valeur.startswith(_PREFIXE):
        raise ValueError("Valeur non chiffrée : refus de la traiter comme une donnée sensible.")
    try:
        return _fernet.decrypt(valeur[len(_PREFIXE):].encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Impossible de déchiffrer : clé ENCRYPTION_KEY différente de celle d'origine ?") from exc


def masquer(valeur: Optional[str], visibles: int = 4) -> str:
    """Affichage masqué (ex. « ••••••••1234 ») d'une valeur en clair."""
    if not valeur:
        return ""
    return "•" * max(0, len(valeur) - visibles) + valeur[-visibles:]
