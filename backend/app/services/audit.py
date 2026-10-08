"""Écriture dans le journal d'audit. Appelé par les routes dès qu'une action est sensible."""
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from ..core.models import JournalAudit, Utilisateur


def adresse_ip(request: Optional[Request]) -> Optional[str]:
    if request is None or request.client is None:
        return None
    return request.client.host


def enregistrer(
    db: Session,
    action: str,
    *,
    acteur: Optional[Utilisateur] = None,
    acteur_identifiant: Optional[str] = None,
    cible_type: Optional[str] = None,
    cible_id: Any = None,
    detail: Optional[dict] = None,
    request: Optional[Request] = None,
) -> None:
    """Ajoute une ligne d'audit à la session ; l'appelant fait le commit avec son action.

    Ne jamais mettre de mot de passe, de jeton ni de donnée sensible en clair dans `detail`.
    """
    db.add(
        JournalAudit(
            acteur_id=acteur.id if acteur else None,
            acteur_identifiant=(acteur.identifiant if acteur else acteur_identifiant),
            action=action,
            cible_type=cible_type,
            cible_id=None if cible_id is None else str(cible_id),
            detail=detail,
            adresse_ip=adresse_ip(request),
        )
    )
