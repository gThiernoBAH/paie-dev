from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ..core import models, schemas
from ..core.database import get_db
from ..services import audit
from ..services import parametres as svc
from .auth_routes import require_permission

router = APIRouter(prefix="/parametres", tags=["Paramétrage"])

DATE_MIN, DATE_MAX = date(1990, 1, 1), date(2100, 12, 31)


def _sortie(p: models.Parametre, jour: Optional[date] = None) -> dict:
    courante = svc.valeur_en_vigueur(p, jour)
    return {
        "cle": p.cle, "categorie": p.categorie, "libelle": p.libelle, "description": p.description,
        "type_valeur": p.type_valeur, "unite": p.unite,
        "valeur_min": None if p.valeur_min is None else float(p.valeur_min),
        "valeur_max": None if p.valeur_max is None else float(p.valeur_max),
        "choix": [c.strip() for c in p.choix.split(",")] if p.choix else None,
        "critique": p.critique,
        "valeur_courante": courante, "nb_valeurs": len(p.valeurs),
    }


def _charger(db: Session, cle: str) -> models.Parametre:
    p = db.get(models.Parametre, cle)
    if p is None:
        raise HTTPException(status_code=404, detail="Paramètre introuvable.")
    return p


@router.get("", response_model=list[schemas.ParametreOut])
def lister(
    categorie: Optional[str] = Query(default=None, max_length=30),
    statut: Optional[str] = Query(default=None, pattern=r"^(confirme|a_confirmer)$"),
    recherche: Optional[str] = Query(default=None, max_length=60),
    db: Session = Depends(get_db),
    _: models.Utilisateur = Depends(require_permission("voir_parametres")),
):
    requete = db.query(models.Parametre)
    if categorie:
        requete = requete.filter(models.Parametre.categorie == categorie)
    lignes = [_sortie(p) for p in requete.order_by(models.Parametre.categorie, models.Parametre.ordre).all()]
    if statut:
        lignes = [l for l in lignes if l["valeur_courante"] and l["valeur_courante"].statut == statut]
    if recherche:
        m = recherche.strip().lower()
        lignes = [l for l in lignes if m in l["libelle"].lower() or m in l["cle"].lower()]
    return lignes


@router.get("/etat", response_model=schemas.EtatParametresOut)
def etat(db: Session = Depends(get_db), _: models.Utilisateur = Depends(require_permission("voir_parametres"))):
    """Synthèse pour le tableau de bord : combien de paramètres restent à confirmer."""
    a_conf = svc.a_confirmer(db)
    critiques = [p.cle for p in a_conf if p.critique]
    return {
        "total": db.query(models.Parametre).count(), "a_confirmer": len(a_conf),
        "critiques_a_confirmer": len(critiques), "cles_critiques": critiques,
    }


@router.get("/{cle}", response_model=schemas.ParametreDetailOut)
def detail(cle: str, db: Session = Depends(get_db), _: models.Utilisateur = Depends(require_permission("voir_parametres"))):
    p = _charger(db, cle)
    return {**_sortie(p), "historique": list(p.valeurs)}


@router.post("/{cle}/valeurs", response_model=schemas.ParametreDetailOut, status_code=201)
def ajouter_valeur(
    cle: str,
    corps: schemas.ValeurParametreIn,
    request: Request,
    db: Session = Depends(get_db),
    acteur: models.Utilisateur = Depends(require_permission("gerer_parametres")),
):
    """Ajoute une valeur « à partir du <date> ». L'historique n'est jamais effacé : seule une valeur
    encore « à confirmer » peut être corrigée à l'identique de date."""
    p = _charger(db, cle)
    if not (DATE_MIN <= corps.date_effet <= DATE_MAX):
        raise HTTPException(status_code=422, detail="Date d'effet invraisemblable.")
    source = (corps.source or "").strip() or None
    if corps.statut == "confirme" and not source:
        raise HTTPException(status_code=422, detail="Pour confirmer une valeur, indiquez sa source (texte de loi, courrier CNPS, note de la direction...).")
    try:
        valeur = svc.normaliser(p, corps.valeur)
    except svc.ValeurInvalide as e:
        raise HTTPException(status_code=422, detail=str(e))

    existante = next((v for v in p.valeurs if v.date_effet == corps.date_effet), None)
    maintenant = datetime.now(timezone.utc)
    confirme = corps.statut == "confirme"
    if existante is not None:
        if existante.statut == "confirme":
            raise HTTPException(
                status_code=409,
                detail="Une valeur confirmée existe déjà à cette date : choisissez une autre date d'effet pour la remplacer.",
            )
        ancienne = existante.valeur
        existante.valeur, existante.statut, existante.source = valeur, corps.statut, source
        existante.commentaire = corps.commentaire
        existante.cree_par = acteur.identifiant
        existante.confirme_par = acteur.identifiant if confirme else None
        existante.confirme_le = maintenant if confirme else None
        action, detail_audit = "parametre_valeur_corrigee", {"ancienne": ancienne}
    else:
        db.add(models.ValeurParametre(
            parametre_cle=cle, valeur=valeur, date_effet=corps.date_effet, statut=corps.statut, source=source,
            commentaire=corps.commentaire, cree_par=acteur.identifiant,
            confirme_par=acteur.identifiant if confirme else None, confirme_le=maintenant if confirme else None,
        ))
        action, detail_audit = "parametre_valeur_ajoutee", {}
    detail_audit.update({"valeur": valeur, "date_effet": corps.date_effet.isoformat(), "statut": corps.statut, "source": source})
    audit.enregistrer(db, action, acteur=acteur, cible_type="parametre", cible_id=cle, detail=detail_audit, request=request)
    db.commit()
    db.refresh(p)
    return {**_sortie(p), "historique": list(p.valeurs)}


@router.post("/{cle}/valeurs/{valeur_id}/confirmer", response_model=schemas.ParametreDetailOut)
def confirmer(
    cle: str,
    valeur_id: int,
    corps: schemas.ConfirmationIn,
    request: Request,
    db: Session = Depends(get_db),
    acteur: models.Utilisateur = Depends(require_permission("gerer_parametres")),
):
    """Un responsable atteste qu'une valeur « à confirmer » est la bonne (sans la modifier)."""
    p = _charger(db, cle)
    v = next((x for x in p.valeurs if x.id == valeur_id), None)
    if v is None:
        raise HTTPException(status_code=404, detail="Valeur introuvable.")
    if v.statut == "confirme":
        raise HTTPException(status_code=409, detail="Cette valeur est déjà confirmée.")
    v.statut, v.source = "confirme", corps.source.strip()
    v.confirme_par, v.confirme_le = acteur.identifiant, datetime.now(timezone.utc)
    audit.enregistrer(
        db, "parametre_valeur_confirmee", acteur=acteur, cible_type="parametre", cible_id=cle,
        detail={"valeur": v.valeur, "date_effet": v.date_effet.isoformat(), "source": v.source}, request=request,
    )
    db.commit()
    db.refresh(p)
    return {**_sortie(p), "historique": list(p.valeurs)}
