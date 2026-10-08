"""Limitation des tentatives de connexion (anti force brute), en mémoire.

Après LOGIN_MAX_ATTEMPTS échecs consécutifs sur un même (identifiant, IP), la connexion est
refusée pendant LOGIN_LOCK_MINUTES. Limite assumée : compteur propre à chaque processus et perdu
au redémarrage ; suffisant pour freiner un essai systématique sur un serveur interne.
"""
import threading
import time

from .settings import settings

_lock = threading.Lock()
_echecs: dict[tuple[str, str], list[float]] = {}


def _cle(identifiant: str, ip: str) -> tuple[str, str]:
    return (identifiant.strip().lower(), ip)


def _purger(cle: tuple[str, str], maintenant: float) -> list[float]:
    fenetre = settings.LOGIN_LOCK_MINUTES * 60
    recents = [t for t in _echecs.get(cle, []) if maintenant - t < fenetre]
    if recents:
        _echecs[cle] = recents
    else:
        _echecs.pop(cle, None)
    return recents


def secondes_restantes(identifiant: str, ip: str) -> int:
    """> 0 si la connexion est verrouillée pour ce couple, sinon 0."""
    maintenant = time.time()
    with _lock:
        recents = _purger(_cle(identifiant, ip), maintenant)
        if len(recents) < settings.LOGIN_MAX_ATTEMPTS:
            return 0
        return max(1, int(settings.LOGIN_LOCK_MINUTES * 60 - (maintenant - recents[0])))


def enregistrer_echec(identifiant: str, ip: str) -> None:
    with _lock:
        _echecs.setdefault(_cle(identifiant, ip), []).append(time.time())


def effacer(identifiant: str, ip: str) -> None:
    with _lock:
        _echecs.pop(_cle(identifiant, ip), None)


def reinitialiser_tout() -> None:
    """Utilisé par les tests."""
    with _lock:
        _echecs.clear()
