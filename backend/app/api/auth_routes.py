from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..core import auth, login_throttle, models, schemas, tokens
from ..core.database import get_db
from ..core.permissions import PERMISSION_REGISTRY
from ..core.settings import settings
from ..services import audit

router = APIRouter(prefix="/auth", tags=["Authentification"])

# Un compte qui doit changer son mot de passe ne peut appeler que ces deux routes.
CHEMINS_CHANGEMENT_MDP = ("/auth/me", "/auth/mot-de-passe")


def utilisateur_vers_sortie(user: models.Utilisateur) -> schemas.UtilisateurOut:
    """Un administrateur porte toutes les permissions ; les autres, celles de la liste blanche."""
    permissions = list(PERMISSION_REGISTRY) if user.role == "admin" else user.cles_permissions
    return schemas.UtilisateurOut(
        id=user.id, identifiant=user.identifiant, nom=user.nom, prenom=user.prenom, email=user.email,
        telephone=user.telephone, role=user.role, est_actif=user.est_actif,
        doit_changer_mot_de_passe=user.doit_changer_mot_de_passe,
        derniere_connexion=user.derniere_connexion, permissions=sorted(permissions),
    )


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.Utilisateur:
    """Jeton signé (Authorization: Bearer ...) vérifié à CHAQUE requête : signature, expiration,
    compte existant et actif, mot de passe inchangé depuis l'émission du jeton."""
    non_authentifie = HTTPException(status_code=401, detail="Non authentifié", headers={"WWW-Authenticate": "Bearer"})
    schema, _, jeton = request.headers.get("Authorization", "").partition(" ")
    if schema.lower() != "bearer" or not jeton:
        raise non_authentifie
    payload = tokens.lire_jeton(jeton.strip())
    if not payload:
        raise non_authentifie
    user = db.get(models.Utilisateur, payload["sub"])
    if not user or not user.est_actif:
        raise non_authentifie
    if payload.get("pwd") != tokens.empreinte_mot_de_passe(user.mot_de_passe_hash):
        raise non_authentifie  # mot de passe changé depuis l'émission du jeton : session révoquée

    if user.doit_changer_mot_de_passe and request.url.path.rstrip("/") not in CHEMINS_CHANGEMENT_MDP:
        raise HTTPException(status_code=403, detail="Vous devez d'abord changer votre mot de passe.")
    return user


def a_la_permission(user: models.Utilisateur, cle: str) -> bool:
    return user.role == "admin" or cle in user.cles_permissions


def require_permission(cle: str):
    """Dépendance FastAPI : exige la permission `cle` (un administrateur les a toutes)."""
    if cle not in PERMISSION_REGISTRY:
        raise ValueError(f"Permission inconnue : {cle}")

    def _verifier(current_user: models.Utilisateur = Depends(get_current_user)) -> models.Utilisateur:
        if not a_la_permission(current_user, cle):
            raise HTTPException(status_code=403, detail="Accès refusé : permission manquante.")
        return current_user

    return _verifier


@router.post("/login", response_model=schemas.SessionOut)
def login(body: schemas.ConnexionIn, request: Request, db: Session = Depends(get_db)):
    identifiant = body.identifiant.strip()
    ip = audit.adresse_ip(request) or "inconnue"

    attente = login_throttle.secondes_restantes(identifiant, ip)
    if attente:
        audit.enregistrer(db, "connexion_bloquee", acteur_identifiant=identifiant, request=request)
        db.commit()
        raise HTTPException(
            status_code=429,
            detail=f"Trop de tentatives. Réessayez dans {max(1, attente // 60 + (1 if attente % 60 else 0))} minute(s).",
        )

    user = db.query(models.Utilisateur).filter(models.Utilisateur.identifiant == identifiant).first()
    if user is None:
        auth.verifier_faux_mot_de_passe(body.password)  # même durée de réponse qu'un vrai refus
        ok = False
    else:
        ok = auth.verify_password(body.password, user.mot_de_passe_hash)

    if not ok or not user.est_actif:
        login_throttle.enregistrer_echec(identifiant, ip)
        audit.enregistrer(db, "connexion_echec", acteur_identifiant=identifiant, request=request)
        db.commit()
        # Même message pour « inconnu », « mauvais mot de passe » et « compte désactivé » : on ne révèle rien.
        raise HTTPException(status_code=401, detail="Identifiant ou mot de passe incorrect.")

    login_throttle.effacer(identifiant, ip)
    user.derniere_connexion = datetime.now(timezone.utc)
    audit.enregistrer(db, "connexion", acteur=user, request=request)
    db.commit()
    jeton, expire = tokens.creer_jeton(user.id, user.mot_de_passe_hash)
    return schemas.SessionOut(access_token=jeton, expires_at=expire, user=utilisateur_vers_sortie(user))


@router.get("/me", response_model=schemas.UtilisateurOut)
def me(current_user: models.Utilisateur = Depends(get_current_user)):
    return utilisateur_vers_sortie(current_user)


@router.post("/mot-de-passe", response_model=schemas.SessionOut)
def changer_mot_de_passe(
    body: schemas.ChangerMotDePasseIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.Utilisateur = Depends(get_current_user),
):
    if not auth.verify_password(body.ancien_mot_de_passe, current_user.mot_de_passe_hash):
        audit.enregistrer(db, "mot_de_passe_refus", acteur=current_user, request=request)
        db.commit()
        raise HTTPException(status_code=400, detail="L'ancien mot de passe est incorrect.")
    if body.nouveau_mot_de_passe == body.ancien_mot_de_passe:
        raise HTTPException(status_code=400, detail="Le nouveau mot de passe doit être différent de l'ancien.")
    erreurs = auth.erreurs_mot_de_passe(body.nouveau_mot_de_passe, current_user.identifiant)
    if erreurs:
        raise HTTPException(status_code=400, detail="Mot de passe trop faible : " + ", ".join(erreurs) + ".")

    current_user.mot_de_passe_hash = auth.get_password_hash(body.nouveau_mot_de_passe)
    current_user.doit_changer_mot_de_passe = False
    current_user.modifie_le = datetime.now(timezone.utc)
    audit.enregistrer(db, "mot_de_passe_change", acteur=current_user, request=request)
    db.commit()
    # L'empreinte du jeton a changé : toutes les anciennes sessions sont révoquées, on en rend une neuve.
    jeton, expire = tokens.creer_jeton(current_user.id, current_user.mot_de_passe_hash)
    return schemas.SessionOut(access_token=jeton, expires_at=expire, user=utilisateur_vers_sortie(current_user))


def require_any_permission(*cles: str):
    """Dépendance FastAPI : exige AU MOINS UNE des permissions listées (un administrateur les a toutes)."""
    for cle in cles:
        if cle not in PERMISSION_REGISTRY:
            raise ValueError(f"Permission inconnue : {cle}")

    def _verifier(current_user: models.Utilisateur = Depends(get_current_user)) -> models.Utilisateur:
        if not any(a_la_permission(current_user, c) for c in cles):
            raise HTTPException(status_code=403, detail="Permission manquante : " + " ou ".join(cles))
        return current_user

    return _verifier
