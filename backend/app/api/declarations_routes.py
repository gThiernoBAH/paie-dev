"""Déclarations (CNPS, ITS, FDFP, DISA) et journal comptable."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..core import models
from ..core.database import get_db
from ..services import audit, compta, declarations, fichiers
from ..services import parametres as param
from .auth_routes import require_permission

router = APIRouter(tags=["Déclarations"])
VOIR = require_permission("voir_declarations")
TYPES = ("cnps", "its", "fdfp", "disa")


def _reponse(titre: str, entetes: list, lignes: list, totaux: Optional[dict], format: str, sous_titre: Optional[str] = None):
    if format == "json":
        return {"titre": titre, "entetes": entetes, "lignes": [[str(v) if not isinstance(v, (str, int, type(None))) else v for v in l] for l in lignes],
                "totaux": {k: str(v) for k, v in (totaux or {}).items()}}
    nom = titre.replace(" ", "_").lower()
    contenu = fichiers.xlsx(titre, entetes, lignes, totaux, sous_titre or titre) if format == "xlsx" else fichiers.csv_fr(entetes, lignes)
    return Response(content=contenu, media_type=fichiers.MEDIA[format], headers={"Content-Disposition": f'attachment; filename="{nom}.{format}"'})


@router.get("/declarations/{type_etat}")
def declaration(type_etat: str, request: Request, annee: int = Query(ge=2000, le=2100), mois: Optional[int] = Query(default=None, ge=1, le=12),
                format: str = Query(default="json", pattern="^(json|xlsx|csv)$"), db: Session = Depends(get_db),
                acteur: models.Utilisateur = Depends(VOIR)):
    if type_etat not in TYPES:
        raise HTTPException(status_code=404, detail="État inconnu.")
    if type_etat != "disa" and mois is None:
        raise HTTPException(status_code=422, detail="Le mois est obligatoire pour cet état.")
    if type_etat == "cnps":
        etat = declarations.etat_cnps(db, annee, mois, param.lire(db, "cnps_plafond_retraite", date(annee, mois, 1)))
    elif type_etat == "its":
        etat = declarations.etat_its(db, annee, mois)
    elif type_etat == "fdfp":
        etat = declarations.etat_fdfp(db, annee, mois)
    else:
        etat = declarations.etat_disa(db, annee)
    if type_etat in ("cnps", "disa"):   # contiennent les numéros CNPS en clair
        audit.enregistrer(db, "declaration_consultee", acteur=acteur, cible_type="declaration", cible_id=etat["titre"],
                          detail={"format": format, "lignes": len(etat["lignes"]), "donnees_sensibles": True}, request=request)
        db.commit()
    return _reponse(etat["titre"], etat["entetes"], etat["lignes"], etat["totaux"], format, f"{param.lire(db, 'entreprise_raison_sociale')} – {etat['titre']}")


@router.get("/campagnes/{campagne_id}/journal-comptable")
def journal(campagne_id: int, request: Request, format: str = Query(default="json", pattern="^(json|xlsx|csv)$"),
            db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(VOIR)):
    c = db.get(models.Campagne, campagne_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Campagne introuvable.")
    if c.statut not in ("validee", "cloturee"):
        raise HTTPException(status_code=409, detail="Le journal n'est généré que pour une campagne validée.")
    ecr = compta.ecritures(db, c)
    entetes = ["Date", "Journal", "Pièce", "Compte", "Libellé", "Débit", "Crédit", "Analytique (service)"]
    lignes = [[e["date"], e["journal"], e["piece"], e["compte"], e["libelle"], e["debit"], e["credit"], e["analytique"]] for e in ecr]
    totaux = {"Débit": sum((e["debit"] for e in ecr), 0), "Crédit": sum((e["credit"] for e in ecr), 0)}
    audit.enregistrer(db, "journal_comptable_genere", acteur=acteur, cible_type="campagne", cible_id=c.id, detail={"format": format}, request=request)
    db.commit()
    if format == "json":
        return {"titre": f"Journal {c.libelle}", "entetes": entetes, "lignes": [[str(v) for v in l] for l in lignes], "totaux": {k: str(v) for k, v in totaux.items()}}
    return _reponse(f"Journal {c.libelle}", entetes, lignes, totaux, format)
