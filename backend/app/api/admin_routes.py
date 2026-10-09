"""Administration : comptes, droits et journal d'audit."""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core import auth, models, schemas
from ..core.database import get_db
from ..core.permissions import PERMISSION_REGISTRY, PERMISSIONS_PAR_DEFAUT, ROLES
from ..services import audit
from ..services import salaries as svc_salaries
from .auth_routes import require_permission, utilisateur_vers_sortie

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/referentiel")
def referentiel(_: models.Utilisateur = Depends(require_permission("gerer_utilisateurs"))):
    """Rôles et permissions disponibles (pour construire l'écran des droits)."""
    return {
        "roles": [{"cle": k, "libelle": v} for k, v in ROLES.items()],
        "permissions": [{"cle": k, "libelle": v} for k, v in PERMISSION_REGISTRY.items()],
        "permissions_par_defaut": PERMISSIONS_PAR_DEFAUT,
    }


@router.get("/utilisateurs", response_model=list[schemas.UtilisateurOut])
def lister_utilisateurs(
    recherche: Optional[str] = Query(default=None, max_length=50),
    db: Session = Depends(get_db),
    _: models.Utilisateur = Depends(require_permission("gerer_utilisateurs")),
):
    requete = db.query(models.Utilisateur)
    if recherche:
        motif = f"%{recherche.strip().lower()}%"
        requete = requete.filter(
            func.lower(models.Utilisateur.identifiant).like(motif)
            | func.lower(models.Utilisateur.nom).like(motif)
            | func.lower(func.coalesce(models.Utilisateur.prenom, "")).like(motif)
        )
    return [utilisateur_vers_sortie(u) for u in requete.order_by(models.Utilisateur.identifiant).limit(500).all()]


def _verifier_role(role: str) -> None:
    if role not in ROLES:
        raise HTTPException(status_code=422, detail=f"Rôle inconnu : {role}.")


def _nombre_admins_actifs(db: Session) -> int:
    return db.query(models.Utilisateur).filter(models.Utilisateur.role == "admin", models.Utilisateur.est_actif.is_(True)).count()


def _fiche_salarie(db: Session, brut: str) -> Optional[models.Salarie]:
    """Fiche salarié correspondant à un identifiant saisi (matricule, zéros initiaux facultatifs), ou None."""
    try:
        matricule = svc_salaries.normaliser_matricule(brut)
    except svc_salaries.MatriculeInvalide:
        return None
    return db.query(models.Salarie).filter_by(matricule=matricule).first()


@router.get("/salarie-par-matricule/{matricule}")
def salarie_par_matricule(
    matricule: str, db: Session = Depends(get_db),
    _: models.Utilisateur = Depends(require_permission("gerer_utilisateurs")),
):
    """Aide à la création d'un compte : si le matricule correspond à un salarié, ses données d'identité
    sont renvoyées pour pré-remplir (et verrouiller) le formulaire."""
    fiche = _fiche_salarie(db, matricule)
    if not fiche:
        return {"existe": False}
    return {
        "existe": True,
        "matricule": fiche.matricule, "nom": fiche.nom, "prenom": fiche.prenoms,
        "email": fiche.email, "telephone": fiche.telephone, "est_actif": fiche.est_actif,
        "compte_existant": db.query(models.Utilisateur).filter_by(identifiant=fiche.matricule).first() is not None,
    }


@router.post("/utilisateurs", response_model=schemas.MotDePasseTemporaireOut, status_code=201)
def creer_utilisateur(
    body: schemas.UtilisateurCreationIn,
    request: Request,
    db: Session = Depends(get_db),
    acteur: models.Utilisateur = Depends(require_permission("gerer_utilisateurs")),
):
    _verifier_role(body.role)
    # Seul un administrateur peut créer un autre administrateur (sinon élévation de privilèges).
    if body.role == "admin" and acteur.role != "admin":
        raise HTTPException(status_code=403, detail="Seul un administrateur peut créer un administrateur.")
    identifiant, nom, prenom = body.identifiant.strip(), body.nom.strip(), (body.prenom or "").strip() or None
    email, telephone = (body.email or "").strip().lower() or None, (body.telephone or "").strip() or None
    # Un matricule connu fait foi : l'identité vient de la fiche salarié, jamais de la saisie (pas d'erreur de recopie).
    fiche = _fiche_salarie(db, identifiant)
    if fiche:
        identifiant, nom, prenom = fiche.matricule, fiche.nom, fiche.prenoms
        email, telephone = (fiche.email or email or "").strip().lower() or None, fiche.telephone or telephone
    mot_de_passe = auth.generer_mot_de_passe_temporaire()
    user = models.Utilisateur(
        identifiant=identifiant,
        nom=nom,
        prenom=prenom,
        email=email,
        telephone=telephone,
        role=body.role,
        mot_de_passe_hash=auth.get_password_hash(mot_de_passe),
        est_actif=True,
        doit_changer_mot_de_passe=True,
    )
    user.permissions = [models.PermissionUtilisateur(permission=p) for p in PERMISSIONS_PAR_DEFAUT.get(body.role, [])]
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Cet identifiant ou cet e-mail existe déjà.")
    audit.enregistrer(
        db, "utilisateur_cree", acteur=acteur, cible_type="utilisateur", cible_id=user.id,
        detail={"identifiant": user.identifiant, "role": user.role}, request=request,
    )
    db.commit()
    db.refresh(user)
    return schemas.MotDePasseTemporaireOut(utilisateur=utilisateur_vers_sortie(user), mot_de_passe_temporaire=mot_de_passe)


def _charger(db: Session, user_id: int) -> models.Utilisateur:
    user = db.get(models.Utilisateur, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")
    return user


@router.patch("/utilisateurs/{user_id}", response_model=schemas.UtilisateurOut)
def modifier_utilisateur(
    user_id: int,
    body: schemas.UtilisateurModificationIn,
    request: Request,
    db: Session = Depends(get_db),
    acteur: models.Utilisateur = Depends(require_permission("gerer_utilisateurs")),
):
    user = _charger(db, user_id)
    changements = body.model_dump(exclude_unset=True)
    avant = {k: getattr(user, k) for k in changements}

    if "role" in changements:
        _verifier_role(changements["role"])
    if (changements.get("role") == "admin" or user.role == "admin") and acteur.role != "admin":
        raise HTTPException(status_code=403, detail="Seul un administrateur peut modifier un compte administrateur.")
    # On ne se retire pas ses propres droits d'administration et on garde au moins un admin actif.
    perd_admin = user.role == "admin" and (changements.get("role", "admin") != "admin" or changements.get("est_actif") is False)
    if perd_admin:
        if user.id == acteur.id:
            raise HTTPException(status_code=400, detail="Vous ne pouvez pas retirer vos propres droits d'administrateur ni désactiver votre compte.")
        if _nombre_admins_actifs(db) <= 1:
            raise HTTPException(status_code=400, detail="Il doit rester au moins un administrateur actif.")
    if changements.get("est_actif") is False and user.id == acteur.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas désactiver votre propre compte.")

    for champ, valeur in changements.items():
        if isinstance(valeur, str):
            valeur = valeur.strip() or None
            if champ == "email" and valeur:
                valeur = valeur.lower()
            if champ == "nom" and valeur is None:
                raise HTTPException(status_code=422, detail="Le nom est obligatoire.")
        setattr(user, champ, valeur)
    user.modifie_le = datetime.now(timezone.utc)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Cet e-mail est déjà utilisé.")
    audit.enregistrer(
        db, "utilisateur_modifie", acteur=acteur, cible_type="utilisateur", cible_id=user.id,
        detail={"avant": {k: str(v) for k, v in avant.items()}, "apres": {k: str(v) for k, v in changements.items()}},
        request=request,
    )
    db.commit()
    db.refresh(user)
    return utilisateur_vers_sortie(user)


@router.put("/utilisateurs/{user_id}/permissions", response_model=schemas.UtilisateurOut)
def definir_permissions(
    user_id: int,
    body: schemas.PermissionsIn,
    request: Request,
    db: Session = Depends(get_db),
    acteur: models.Utilisateur = Depends(require_permission("gerer_utilisateurs")),
):
    user = _charger(db, user_id)
    inconnues = sorted(set(body.permissions) - set(PERMISSION_REGISTRY))
    if inconnues:
        raise HTTPException(status_code=422, detail="Permissions inconnues : " + ", ".join(inconnues))
    if user.role == "admin" and acteur.role != "admin":
        raise HTTPException(status_code=403, detail="Seul un administrateur peut modifier un compte administrateur.")
    # On n'accorde pas une permission qu'on ne possède pas soi-même (pas d'élévation de privilèges).
    nouvelles = set(body.permissions)
    for cle in nouvelles - set(user.cles_permissions):
        if acteur.role != "admin" and cle not in acteur.cles_permissions:
            raise HTTPException(status_code=403, detail=f"Vous ne pouvez pas accorder une permission que vous n'avez pas ({cle}).")
    avant = user.cles_permissions
    user.permissions = [models.PermissionUtilisateur(permission=p) for p in sorted(nouvelles)]
    user.modifie_le = datetime.now(timezone.utc)
    audit.enregistrer(
        db, "permissions_modifiees", acteur=acteur, cible_type="utilisateur", cible_id=user.id,
        detail={"avant": avant, "apres": sorted(nouvelles)}, request=request,
    )
    db.commit()
    db.refresh(user)
    return utilisateur_vers_sortie(user)


@router.post("/utilisateurs/{user_id}/reinitialiser-mot-de-passe", response_model=schemas.MotDePasseTemporaireOut)
def reinitialiser_mot_de_passe(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    acteur: models.Utilisateur = Depends(require_permission("gerer_utilisateurs")),
):
    user = _charger(db, user_id)
    if user.role == "admin" and acteur.role != "admin":
        raise HTTPException(status_code=403, detail="Seul un administrateur peut réinitialiser un compte administrateur.")
    mot_de_passe = auth.generer_mot_de_passe_temporaire()
    user.mot_de_passe_hash = auth.get_password_hash(mot_de_passe)
    user.doit_changer_mot_de_passe = True
    user.modifie_le = datetime.now(timezone.utc)
    audit.enregistrer(db, "mot_de_passe_reinitialise", acteur=acteur, cible_type="utilisateur", cible_id=user.id, request=request)
    db.commit()
    db.refresh(user)
    return schemas.MotDePasseTemporaireOut(utilisateur=utilisateur_vers_sortie(user), mot_de_passe_temporaire=mot_de_passe)


@router.get("/audit", response_model=schemas.AuditPageOut)
def consulter_audit(
    page: int = Query(default=1, ge=1),
    taille: int = Query(default=50, ge=1, le=200),
    action: Optional[str] = Query(default=None, max_length=60),
    acteur: Optional[str] = Query(default=None, max_length=20),
    du: Optional[date] = None,
    au: Optional[date] = None,
    tri: str = Query(default="id", pattern=r"^(id|horodatage|acteur_identifiant|action|cible_type|adresse_ip)$"),
    sens: str = Query(default="desc", pattern=r"^(asc|desc)$"),
    db: Session = Depends(get_db),
    consultant: models.Utilisateur = Depends(require_permission("voir_audit")),
):
    requete = db.query(models.JournalAudit)
    if action:
        requete = requete.filter(models.JournalAudit.action == action)
    if acteur:
        requete = requete.filter(models.JournalAudit.acteur_identifiant == acteur)
    if du:
        requete = requete.filter(models.JournalAudit.horodatage >= datetime.combine(du, datetime.min.time(), tzinfo=timezone.utc))
    if au:
        requete = requete.filter(
            models.JournalAudit.horodatage < datetime.combine(au + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        )
    total = requete.count()
    cle = getattr(models.JournalAudit, tri)
    ordre = cle.desc().nulls_last() if sens == "desc" else cle.asc().nulls_last()
    lignes = requete.order_by(ordre, models.JournalAudit.id.desc()).offset((page - 1) * taille).limit(taille).all()
    return schemas.AuditPageOut(total=total, page=page, taille=taille, elements=lignes)
