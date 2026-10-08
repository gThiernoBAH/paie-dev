from datetime import date, time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core import models, schemas
from ..core.database import get_db
from ..services import audit, import_pointages
from ..services import presences as svc_presences
from .auth_routes import require_any_permission, require_permission

router = APIRouter(tags=["Pointages"])


def _hh(t: Optional[time]) -> Optional[str]:
    return None if t is None else t.strftime("%H:%M")


def _vers_heure(texte: Optional[str]) -> Optional[time]:
    return None if not texte else time(int(texte[:2]), int(texte[3:5]))


def _sortie(p: models.Pointage, s: models.Salarie) -> dict:
    return {"id": p.id, "salarie_id": s.id, "matricule": s.matricule, "nom": f"{s.nom} {s.prenoms or ''}".strip(),
            "jour": p.jour, "heure_entree": _hh(p.heure_entree), "heure_sortie": _hh(p.heure_sortie),
            "source": p.source, "commentaire": p.commentaire}


@router.get("/pointages", response_model=list[schemas.PointageOut])
def lister(
    du: date, au: date, salarie_id: Optional[int] = None, limite: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db), _: models.Utilisateur = Depends(require_permission("gerer_pointages")),
):
    if (au - du).days > 93:
        raise HTTPException(status_code=422, detail="Période trop longue (93 jours maximum).")
    requete = db.query(models.Pointage, models.Salarie).join(models.Salarie).filter(
        models.Pointage.jour >= du, models.Pointage.jour <= au)
    if salarie_id:
        requete = requete.filter(models.Pointage.salarie_id == salarie_id)
    lignes = requete.order_by(models.Pointage.jour, models.Salarie.matricule).limit(limite).all()
    return [_sortie(p, s) for p, s in lignes]


@router.put("/pointages", response_model=schemas.PointageOut)
def saisir(
    corps: schemas.PointageIn, request: Request, db: Session = Depends(get_db),
    acteur: models.Utilisateur = Depends(require_permission("gerer_pointages")),
):
    """Création ou correction manuelle d'un pointage (une ligne par salarié et par jour)."""
    s = db.get(models.Salarie, corps.salarie_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Salarié introuvable.")
    p = db.query(models.Pointage).filter_by(salarie_id=s.id, jour=corps.jour).first()
    avant = None if p is None else {"entree": _hh(p.heure_entree), "sortie": _hh(p.heure_sortie)}
    if p is None:
        p = models.Pointage(salarie_id=s.id, jour=corps.jour)
        db.add(p)
    p.heure_entree, p.heure_sortie = _vers_heure(corps.heure_entree), _vers_heure(corps.heure_sortie)
    p.source, p.commentaire, p.cree_par, p.modifie_le = "manuel", corps.commentaire, acteur.identifiant, func.now()
    db.flush()
    audit.enregistrer(db, "pointage_saisi", acteur=acteur, cible_type="salarie", cible_id=s.id,
                      detail={"matricule": s.matricule, "jour": corps.jour.isoformat(), "avant": avant,
                              "apres": {"entree": corps.heure_entree, "sortie": corps.heure_sortie}}, request=request)
    db.commit()
    db.refresh(p)
    return _sortie(p, s)


@router.delete("/pointages/{pointage_id}", status_code=204)
def supprimer(pointage_id: int, request: Request, db: Session = Depends(get_db),
              acteur: models.Utilisateur = Depends(require_permission("gerer_pointages"))):
    p = db.get(models.Pointage, pointage_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Pointage introuvable.")
    s = db.get(models.Salarie, p.salarie_id)
    audit.enregistrer(db, "pointage_supprime", acteur=acteur, cible_type="salarie", cible_id=s.id,
                      detail={"matricule": s.matricule, "jour": p.jour.isoformat()}, request=request)
    db.delete(p)
    db.commit()


@router.post("/pointages/import")
def importer(
    corps: schemas.ImportPointagesIn, request: Request, db: Session = Depends(get_db),
    acteur: models.Utilisateur = Depends(require_permission("gerer_pointages")),
):
    """Importe un fichier CSV de pointages. Un jour déjà pointé est remplacé par le fichier ; les lignes
    invalides sont rejetées et listées, sans bloquer le reste."""
    try:
        jours, rejets, nb_lignes = import_pointages.lire(corps.contenu)
    except import_pointages.FichierInvalide as e:
        raise HTTPException(status_code=422, detail=str(e))
    par_matricule = {s.matricule: s for s in db.query(models.Salarie).filter(
        models.Salarie.matricule.in_({m for m, _ in jours})).all()}
    imp = models.ImportPointages(nom_fichier=corps.nom_fichier, importe_par=acteur.identifiant, nb_lignes=nb_lignes)
    db.add(imp)
    db.flush()
    importes = 0
    for (matricule, jour), (entree, sortie) in sorted(jours.items(), key=lambda x: (x[0][1], x[0][0])):
        s = par_matricule.get(matricule)
        if s is None:
            rejets.append({"ligne": None, "motif": f"matricule inconnu {matricule}"})
            continue
        p = db.query(models.Pointage).filter_by(salarie_id=s.id, jour=jour).first()
        if p is None:
            p = models.Pointage(salarie_id=s.id, jour=jour)
            db.add(p)
        p.heure_entree, p.heure_sortie, p.source, p.import_id = entree, sortie, "import", imp.id
        p.cree_par, p.modifie_le = acteur.identifiant, func.now()
        importes += 1
    imp.nb_jours, imp.nb_rejets, imp.rejets = importes, len(rejets), rejets[:200]
    audit.enregistrer(db, "pointages_importes", acteur=acteur, cible_type="import_pointages", cible_id=imp.id,
                      detail={"fichier": corps.nom_fichier, "jours": importes, "rejets": len(rejets)}, request=request)
    db.commit()
    return {"import_id": imp.id, "lignes_lues": nb_lignes, "jours_importes": importes, "rejets": rejets[:200], "nb_rejets": len(rejets)}


@router.get("/pointages/imports")
def historique_imports(db: Session = Depends(get_db), _: models.Utilisateur = Depends(require_permission("gerer_pointages"))):
    return [{"id": i.id, "nom_fichier": i.nom_fichier, "importe_par": i.importe_par, "importe_le": i.importe_le,
             "nb_lignes": i.nb_lignes, "nb_jours": i.nb_jours, "nb_rejets": i.nb_rejets}
            for i in db.query(models.ImportPointages).order_by(models.ImportPointages.id.desc()).limit(50).all()]


@router.get("/presences/calcul")
def calcul_presences(
    salarie_id: int, du: date, au: date, db: Session = Depends(get_db),
    _: models.Utilisateur = Depends(require_permission("gerer_pointages")),
):
    """Présences calculées pour un salarié sur une période (aperçu avant de les appliquer à une campagne)."""
    s = db.get(models.Salarie, salarie_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Salarié introuvable.")
    if au < du or (au - du).days > 93:
        raise HTTPException(status_code=422, detail="Période invalide (93 jours maximum).")
    r = svc_presences.calculer(db, s, du, au)
    return {
        "matricule": s.matricule, "jours_presence": r.jours_presence, "heures_normales": float(r.heures_normales),
        "heures_sup": {str(k): float(v) for k, v in r.heures_sup.items()},
        "absences_detectees": r.absences_detectees, "pointages_incomplets": r.jours_sans_sortie,
        "detail": [{**x} for x in r.detail],
    }


# --- Jours fériés ---
@router.get("/jours-feries")
def lister_feries(annee: Optional[int] = None, db: Session = Depends(get_db),
                  _: models.Utilisateur = Depends(require_permission("gerer_pointages"))):
    q = db.query(models.JourFerie)
    if annee:
        q = q.filter(models.JourFerie.jour >= date(annee, 1, 1), models.JourFerie.jour <= date(annee, 12, 31))
    return [{"jour": f.jour, "libelle": f.libelle} for f in q.order_by(models.JourFerie.jour).all()]


@router.post("/jours-feries", status_code=201)
def ajouter_ferie(corps: schemas.JourFerieIn, request: Request, db: Session = Depends(get_db),
                  acteur: models.Utilisateur = Depends(require_permission("gerer_pointages"))):
    if db.get(models.JourFerie, corps.jour):
        raise HTTPException(status_code=409, detail="Ce jour férié existe déjà.")
    db.add(models.JourFerie(jour=corps.jour, libelle=corps.libelle.strip()))
    audit.enregistrer(db, "jour_ferie_ajoute", acteur=acteur, cible_type="jour_ferie", cible_id=corps.jour.isoformat(),
                      detail={"libelle": corps.libelle}, request=request)
    db.commit()
    return {"jour": corps.jour, "libelle": corps.libelle}


@router.delete("/jours-feries/{jour}", status_code=204)
def supprimer_ferie(jour: date, request: Request, db: Session = Depends(get_db),
                    acteur: models.Utilisateur = Depends(require_permission("gerer_pointages"))):
    f = db.get(models.JourFerie, jour)
    if f is None:
        raise HTTPException(status_code=404, detail="Jour férié introuvable.")
    audit.enregistrer(db, "jour_ferie_supprime", acteur=acteur, cible_type="jour_ferie", cible_id=jour.isoformat(), request=request)
    db.delete(f)
    db.commit()


# --- Rubriques variables ---
@router.get("/rubriques")
def lister_rubriques(inclure_inactives: bool = False, db: Session = Depends(get_db),
                     _: models.Utilisateur = Depends(require_any_permission("voir_salaries", "lancer_paie"))):
    q = db.query(models.Rubrique)
    if not inclure_inactives:
        q = q.filter(models.Rubrique.est_actif.is_(True))
    return [{"code": r.code, "libelle": r.libelle, "type": r.type,
             "montant_defaut": None if r.montant_defaut is None else float(r.montant_defaut), "est_actif": r.est_actif}
            for r in q.order_by(models.Rubrique.code).all()]


@router.post("/rubriques", status_code=201)
def creer_rubrique(corps: schemas.RubriqueIn, request: Request, db: Session = Depends(get_db),
                   acteur: models.Utilisateur = Depends(require_permission("gerer_parametres"))):
    code = corps.code.upper()
    if db.get(models.Rubrique, code):
        raise HTTPException(status_code=409, detail="Ce code de rubrique existe déjà.")
    db.add(models.Rubrique(code=code, libelle=corps.libelle.strip(), type=corps.type, montant_defaut=corps.montant_defaut))
    audit.enregistrer(db, "rubrique_creee", acteur=acteur, cible_type="rubrique", cible_id=code, detail={"type": corps.type}, request=request)
    db.commit()
    return {"code": code, "libelle": corps.libelle, "type": corps.type, "montant_defaut": corps.montant_defaut, "est_actif": True}


@router.patch("/rubriques/{code}")
def modifier_rubrique(code: str, corps: schemas.RubriqueModifIn, request: Request, db: Session = Depends(get_db),
                      acteur: models.Utilisateur = Depends(require_permission("gerer_parametres"))):
    r = db.get(models.Rubrique, code.upper())
    if r is None:
        raise HTTPException(status_code=404, detail="Rubrique introuvable.")
    changements = corps.model_dump(exclude_unset=True)
    for k, v in changements.items():
        setattr(r, k, v)
    audit.enregistrer(db, "rubrique_modifiee", acteur=acteur, cible_type="rubrique", cible_id=r.code, detail={"champs": sorted(changements)}, request=request)
    db.commit()
    return {"code": r.code, "libelle": r.libelle, "type": r.type,
            "montant_defaut": None if r.montant_defaut is None else float(r.montant_defaut), "est_actif": r.est_actif}
