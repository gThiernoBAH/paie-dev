"""Règles métier de la fiche salarié (matricule, parts fiscales, salaire en vigueur)."""
import re
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from ..core.models import Salarie


class MatriculeInvalide(ValueError):
    pass


def normaliser_matricule(brut: str) -> str:
    """6 chiffres, zéros initiaux conservés : '54' -> '000054'."""
    v = (brut or "").strip()
    if not re.fullmatch(r"\d{1,6}", v):
        raise MatriculeInvalide("Le matricule doit comporter 1 à 6 chiffres (il sera complété par des zéros).")
    return v.zfill(6)


def prochain_matricule(db: Session) -> str:
    """Plus grand matricule + 1 (les trous ne sont pas réutilisés : un matricule n'est jamais recyclé)."""
    plus_grand = max((int(m) for (m,) in db.query(Salarie.matricule).all()), default=0)
    if plus_grand >= 999999:
        raise MatriculeInvalide("Plus de matricule disponible.")
    return str(plus_grand + 1).zfill(6)


def parts_suggerees(situation: str, enfants: int) -> Decimal:
    """Nombre de parts proposé (CGI ivoirien, à confirmer). Toujours modifiable sur la fiche.

    Marié : 2 parts + 0,5 par enfant. Célibataire, divorcé ou veuf : 1 part ; avec enfants,
    +1 pour le premier puis +0,5 par enfant suivant. Maximum 5.
    """
    enfants = max(0, enfants)
    if situation == "marie":
        parts = Decimal(2) + Decimal("0.5") * enfants
    else:
        parts = Decimal(1)
        if enfants:
            parts += 1 + Decimal("0.5") * (enfants - 1)
    return min(parts, Decimal(5))


def salaire_en_vigueur(salarie: Salarie, a_la_date: Optional[date] = None):
    jour = a_la_date or date.today()
    for e in salarie.evolutions:  # triées par date d'effet décroissante
        if e.date_effet <= jour:
            return e
    return None
