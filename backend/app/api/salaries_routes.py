import re
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core import auth, crypto, models, schemas
from ..core.database import get_db
from ..core.permissions import PERMISSIONS_PAR_DEFAUT
from ..services import audit
from ..services import salaries as svc
from .auth_routes import a_la_permission, require_permission, utilisateur_vers_sortie

router = APIRouter(prefix="/salaries", tags=["Salariés"])

# champ de la fiche -> type de référentiel attendu
LIENS = {
    "type_contrat_id": "type_contrat", "service_id": "service", "section_id": "section",
    "emploi_id": "emploi", "categorie_id": "categorie", "site_id": "site", "banque_id": "banque",
}


def _charger(db: Session, salarie_id: int) -> models.Salarie:
    s = db.get(models.Salarie, salarie_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Salarié introuvable.")
    return s


def _ref(r):
    return None if r is None else {"id": r.id, "code": r.code, "libelle": r.libelle}


def _fiche(s: models.Salarie, sensible: bool) -> dict:
    sortie = {
        "id": s.id, "matricule": s.matricule, "nom": s.nom, "prenoms": s.prenoms, "sexe": s.sexe,
        "date_naissance": s.date_naissance, "lieu_naissance": s.lieu_naissance, "nationalite": s.nationalite,
        "situation_matrimoniale": s.situation_matrimoniale, "nombre_enfants": s.nombre_enfants,
        "nombre_parts": float(s.nombre_parts), "nombre_personnes_cmu": s.nombre_personnes_cmu,
        "telephone": s.telephone, "email": s.email, "adresse": s.adresse, "ville": s.ville,
        "date_embauche": s.date_embauche, "date_sortie": s.date_sortie, "motif_sortie": s.motif_sortie,
        "type_contrat": _ref(s.type_contrat), "service": _ref(s.service), "section": _ref(s.section),
        "emploi": _ref(s.emploi), "categorie": _ref(s.categorie), "site": _ref(s.site), "banque": _ref(s.banque),
        "type_remuneration": s.type_remuneration, "eligible_heures_sup": s.eligible_heures_sup,
        "mode_paiement": s.mode_paiement, "est_actif": s.est_actif,
        "a_un_rib": bool(s.rib_chiffre), "a_un_numero_cnps": bool(s.numero_cnps_chiffre),
        "donnees_sensibles_visibles": sensible, "salaire_actuel": None,
    }
    if sensible:
        e = svc.salaire_en_vigueur(s)
        sortie["salaire_actuel"] = None if e is None else {"montant": float(e.montant), "date_effet": e.date_effet}
    return sortie


def _verifier_liens(db: Session, valeurs: dict) -> None:
    for champ, type_attendu in LIENS.items():
        rid = valeurs.get(champ)
        if rid is None:
            continue
        ref = db.get(models.Referentiel, rid)
        if ref is None or ref.type_ref != type_attendu or not ref.est_actif:
            raise HTTPException(status_code=422, detail=f"Valeur invalide pour « {champ.removesuffix('_id')} ».")


def _nettoyer(valeurs: dict) -> dict:
    return {k: (v.strip() or None) if isinstance(v, str) else v for k, v in valeurs.items()}


def _rib(brut: str) -> str:
    v = re.sub(r"[\s\-]", "", brut).upper()
    if not re.fullmatch(r"[A-Z0-9]{15,30}", v):
        raise HTTPException(status_code=422, detail="RIB invalide : 15 à 30 lettres ou chiffres attendus.")
    return v


@router.get("/prochain-matricule")
def prochain_matricule(db: Session = Depends(get_db), _: models.Utilisateur = Depends(require_permission("modifier_salaries"))):
    return {"matricule": svc.prochain_matricule(db)}


@router.get("/parts-suggerees")
def parts_suggerees(
    situation: str = Query(pattern=r"^(celibataire|marie|divorce|veuf)$"), enfants: int = Query(ge=0, le=30),
    _: models.Utilisateur = Depends(require_permission("voir_salaries")),
):
    return {"parts": float(svc.parts_suggerees(situation, enfants))}


@router.get("", response_model=schemas.SalariePageOut)
def lister(
    recherche: Optional[str] = Query(default=None, max_length=60),
    service_id: Optional[int] = None,
    type_remuneration: Optional[str] = Query(default=None, pattern=r"^(mensuel|journalier)$"),
    statut: str = Query(default="actifs", pattern=r"^(actifs|sortis|tous)$"),
    page: int = Query(default=1, ge=1), taille: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: models.Utilisateur = Depends(require_permission("voir_salaries")),
):
    requete = db.query(models.Salarie)
    if recherche:
        m = f"%{recherche.strip().lower()}%"
        requete = requete.filter(or_(
            models.Salarie.matricule.like(f"%{recherche.strip()}%"),
            models.Salarie.nom.ilike(m), models.Salarie.prenoms.ilike(m),
        ))
    if service_id:
        requete = requete.filter(models.Salarie.service_id == service_id)
    if type_remuneration:
        requete = requete.filter(models.Salarie.type_remuneration == type_remuneration)
    if statut != "tous":
        requete = requete.filter(models.Salarie.est_actif.is_(statut == "actifs"))
    total = requete.count()
    lignes = requete.order_by(models.Salarie.matricule).offset((page - 1) * taille).limit(taille).all()
    return {"total": total, "page": page, "taille": taille, "elements": lignes}


@router.post("", status_code=201)
def creer(
    corps: schemas.SalarieCreationIn, request: Request, db: Session = Depends(get_db),
    acteur: models.Utilisateur = Depends(require_permission("modifier_salaries")),
):
    sensible = a_la_permission(acteur, "voir_donnees_sensibles")
    donnees = _nettoyer(corps.model_dump(exclude_unset=True, exclude={"matricule", "salaire_base", "rib", "numero_cnps"}))
    if (corps.rib or corps.numero_cnps or corps.salaire_base is not None) and not sensible:
        raise HTTPException(status_code=403, detail="Le RIB, le n° CNPS et le salaire exigent le droit « données sensibles ».")
    _verifier_liens(db, donnees)
    try:
        matricule = svc.normaliser_matricule(corps.matricule) if corps.matricule else svc.prochain_matricule(db)
    except svc.MatriculeInvalide as e:
        raise HTTPException(status_code=422, detail=str(e))
    if db.query(models.Salarie).filter_by(matricule=matricule).first():
        raise HTTPException(status_code=409, detail=f"Le matricule {matricule} existe déjà.")
    salarie = models.Salarie(matricule=matricule, **donnees)
    if "nombre_parts" not in donnees:
        salarie.nombre_parts = svc.parts_suggerees(salarie.situation_matrimoniale or "celibataire", salarie.nombre_enfants or 0)
    if corps.rib:
        salarie.rib_chiffre = crypto.chiffrer(_rib(corps.rib))
    if corps.numero_cnps:
        salarie.numero_cnps_chiffre = crypto.chiffrer(corps.numero_cnps.strip())
    if corps.salaire_base is not None:
        salarie.evolutions.append(models.EvolutionSalaire(
            date_effet=salarie.date_embauche or date.today(), montant=corps.salaire_base,
            motif="Salaire d'embauche", cree_par=acteur.identifiant))
    db.add(salarie)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Fiche en conflit (matricule ou valeur déjà utilisée).")
    audit.enregistrer(db, "salarie_cree", acteur=acteur, cible_type="salarie", cible_id=salarie.id,
                      detail={"matricule": salarie.matricule}, request=request)
    db.commit()
    db.refresh(salarie)
    return _fiche(salarie, sensible)


@router.get("/{salarie_id}")
def fiche(salarie_id: int, db: Session = Depends(get_db), acteur: models.Utilisateur = Depends(require_permission("voir_salaries"))):
    return _fiche(_charger(db, salarie_id), a_la_permission(acteur, "voir_donnees_sensibles"))


@router.patch("/{salarie_id}")
def modifier(
    salarie_id: int, corps: schemas.SalarieChampsIn, request: Request, db: Session = Depends(get_db),
    acteur: models.Utilisateur = Depends(require_permission("modifier_salaries")),
):
    s = _charger(db, salarie_id)
    sensible = a_la_permission(acteur, "voir_donnees_sensibles")
    envoyes = corps.model_dump(exclude_unset=True)
    if ("rib" in envoyes or "numero_cnps" in envoyes) and not sensible:
        raise HTTPException(status_code=403, detail="Le RIB et le n° CNPS exigent le droit « données sensibles ».")
    rib, cnps = envoyes.pop("rib", None), envoyes.pop("numero_cnps", None)
    a_rib, a_cnps = "rib" in corps.model_fields_set, "numero_cnps" in corps.model_fields_set
    donnees = _nettoyer(envoyes)
    if "nom" in donnees and not donnees["nom"]:
        raise HTTPException(status_code=422, detail="Le nom est obligatoire.")
    _verifier_liens(db, {k: v for k, v in donnees.items() if k in LIENS and v != getattr(s, k)})
    for champ, valeur in donnees.items():
        setattr(s, champ, valeur)
    if ("situation_matrimoniale" in donnees or "nombre_enfants" in donnees) and "nombre_parts" not in donnees:
        s.nombre_parts = svc.parts_suggerees(s.situation_matrimoniale, s.nombre_enfants)
    champs = sorted(donnees)
    if a_rib:
        s.rib_chiffre = crypto.chiffrer(_rib(rib)) if rib else None
        champs.append("rib")
    if a_cnps:
        s.numero_cnps_chiffre = crypto.chiffrer(cnps.strip()) if cnps else None
        champs.append("numero_cnps")
    if s.date_sortie and s.date_embauche and s.date_sortie < s.date_embauche:
        raise HTTPException(status_code=422, detail="La date de sortie précède la date d'embauche.")
    from sqlalchemy.sql import func
    s.modifie_le = func.now()
    # Le journal garde le NOM des champs modifiés, jamais leur valeur (données personnelles).
    audit.enregistrer(db, "salarie_modifie", acteur=acteur, cible_type="salarie", cible_id=s.id,
                      detail={"matricule": s.matricule, "champs": sorted(champs)}, request=request)
    db.commit()
    db.refresh(s)
    return _fiche(s, sensible)


@router.get("/{salarie_id}/donnees-sensibles")
def donnees_sensibles(
    salarie_id: int, request: Request, db: Session = Depends(get_db),
    acteur: models.Utilisateur = Depends(require_permission("voir_donnees_sensibles")),
):
    """RIB et n° CNPS en clair : chaque consultation est tracée dans le journal d'audit."""
    s = _charger(db, salarie_id)
    audit.enregistrer(db, "salarie_donnees_sensibles_consultees", acteur=acteur, cible_type="salarie",
                      cible_id=s.id, detail={"matricule": s.matricule}, request=request)
    db.commit()
    return {"rib": crypto.dechiffrer(s.rib_chiffre), "numero_cnps": crypto.dechiffrer(s.numero_cnps_chiffre)}


@router.get("/{salarie_id}/salaires", response_model=list[schemas.EvolutionSalaireOut])
def historique_salaire(salarie_id: int, db: Session = Depends(get_db), _: models.Utilisateur = Depends(require_permission("voir_donnees_sensibles"))):
    return list(_charger(db, salarie_id).evolutions)


@router.post("/{salarie_id}/salaires", response_model=list[schemas.EvolutionSalaireOut], status_code=201)
def ajouter_salaire(
    salarie_id: int, corps: schemas.EvolutionSalaireIn, request: Request, db: Session = Depends(get_db),
    acteur: models.Utilisateur = Depends(require_permission("voir_donnees_sensibles")),
):
    """Nouveau salaire « à partir du ... ». Une date déjà utilisée est refusée (on ne réécrit pas l'historique)."""
    if not acteur_peut_modifier(acteur):
        raise HTTPException(status_code=403, detail="Permission manquante : modifier_salaries")
    s = _charger(db, salarie_id)
    if any(e.date_effet == corps.date_effet for e in s.evolutions):
        raise HTTPException(status_code=409, detail="Un salaire existe déjà à cette date : choisissez une autre date d'effet.")
    s.evolutions.append(models.EvolutionSalaire(
        date_effet=corps.date_effet, montant=corps.montant, motif=corps.motif, cree_par=acteur.identifiant))
    audit.enregistrer(db, "salaire_modifie", acteur=acteur, cible_type="salarie", cible_id=s.id,
                      detail={"matricule": s.matricule, "date_effet": corps.date_effet.isoformat()}, request=request)
    db.commit()
    db.refresh(s)
    return list(s.evolutions)


def acteur_peut_modifier(acteur: models.Utilisateur) -> bool:
    return a_la_permission(acteur, "modifier_salaries")


@router.post("/{salarie_id}/sortie")
def enregistrer_sortie(
    salarie_id: int, corps: schemas.SortieIn, request: Request, db: Session = Depends(get_db),
    acteur: models.Utilisateur = Depends(require_permission("modifier_salaries")),
):
    """Départ du salarié. Il reste consultable ; son compte de connexion est désactivé."""
    s = _charger(db, salarie_id)
    if s.date_embauche and corps.date_sortie < s.date_embauche:
        raise HTTPException(status_code=422, detail="La date de sortie précède la date d'embauche.")
    s.date_sortie, s.motif_sortie, s.est_actif = corps.date_sortie, corps.motif_sortie.strip(), False
    compte = db.query(models.Utilisateur).filter_by(identifiant=s.matricule, role="salarie").first()
    if compte:
        compte.est_actif = False
    audit.enregistrer(db, "salarie_sortie", acteur=acteur, cible_type="salarie", cible_id=s.id,
                      detail={"matricule": s.matricule, "motif": s.motif_sortie, "date": corps.date_sortie.isoformat()}, request=request)
    db.commit()
    db.refresh(s)
    return _fiche(s, a_la_permission(acteur, "voir_donnees_sensibles"))


@router.post("/{salarie_id}/reactiver")
def reactiver(
    salarie_id: int, request: Request, db: Session = Depends(get_db),
    acteur: models.Utilisateur = Depends(require_permission("modifier_salaries")),
):
    s = _charger(db, salarie_id)
    s.est_actif, s.date_sortie, s.motif_sortie = True, None, None
    audit.enregistrer(db, "salarie_reactive", acteur=acteur, cible_type="salarie", cible_id=s.id,
                      detail={"matricule": s.matricule}, request=request)
    db.commit()
    db.refresh(s)
    return _fiche(s, a_la_permission(acteur, "voir_donnees_sensibles"))


@router.post("/{salarie_id}/creer-compte", status_code=201)
def creer_compte(
    salarie_id: int, request: Request, db: Session = Depends(get_db),
    acteur: models.Utilisateur = Depends(require_permission("gerer_utilisateurs")),
):
    """Ouvre l'accès « espace salarié » : identifiant = matricule, mot de passe temporaire affiché une fois."""
    if not a_la_permission(acteur, "modifier_salaries"):
        raise HTTPException(status_code=403, detail="Permission manquante : modifier_salaries")
    s = _charger(db, salarie_id)
    if not s.est_actif:
        raise HTTPException(status_code=409, detail="Ce salarié n'est plus en activité.")
    mot_de_passe = auth.generer_mot_de_passe_temporaire()
    user = models.Utilisateur(
        identifiant=s.matricule, nom=s.nom, prenom=s.prenoms, email=(s.email or "").lower() or None,
        telephone=s.telephone, role="salarie", mot_de_passe_hash=auth.get_password_hash(mot_de_passe),
        est_actif=True, doit_changer_mot_de_passe=True,
    )
    user.permissions = [models.PermissionUtilisateur(permission=p) for p in PERMISSIONS_PAR_DEFAUT["salarie"]]
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Un compte existe déjà pour ce matricule (ou cet e-mail est déjà utilisé).")
    audit.enregistrer(db, "utilisateur_cree", acteur=acteur, cible_type="utilisateur", cible_id=user.id,
                      detail={"identifiant": user.identifiant, "role": "salarie", "depuis_fiche_salarie": True}, request=request)
    db.commit()
    db.refresh(user)
    return {"utilisateur": utilisateur_vers_sortie(user), "mot_de_passe_temporaire": mot_de_passe}
