"""Rubriques fixes : primes ou retenues récurrentes d'un salarié, ajoutées à chaque bulletin mensuel."""
from datetime import date
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core import models
from ..moteur.modeles import Rubrique


class ErreurRubriqueFixe(ValueError):
    pass


def en_vigueur(db: Session, salarie_id: int, debut: date, fin: date) -> list:
    """Rubriques fixes actives qui recouvrent la période [debut, fin]."""
    return db.query(models.RubriqueFixe).filter(
        models.RubriqueFixe.salarie_id == salarie_id, models.RubriqueFixe.est_actif.is_(True),
        models.RubriqueFixe.date_debut <= fin,
        or_(models.RubriqueFixe.date_fin.is_(None), models.RubriqueFixe.date_fin >= debut),
    ).order_by(models.RubriqueFixe.id).all()


def rubriques_du_mois(db: Session, salarie_id: int, debut: date, fin: date) -> list:
    """Les rubriques fixes sous la forme attendue par le moteur de calcul."""
    return [Rubrique(f.code, (f.rubrique.libelle + (f" ({f.commentaire})" if f.commentaire else ""))[:100], f.rubrique.type, f.montant)
            for f in en_vigueur(db, salarie_id, debut, fin)]


def creer(db: Session, salarie: models.Salarie, code: str, montant, date_debut: date, date_fin: Optional[date],
          commentaire: Optional[str], acteur: models.Utilisateur) -> models.RubriqueFixe:
    rub = db.get(models.Rubrique, code.strip().upper())
    if rub is None or not rub.est_actif:
        raise ErreurRubriqueFixe(f"Rubrique « {code} » inconnue ou désactivée.")
    if date_fin and date_fin < date_debut:
        raise ErreurRubriqueFixe("La fin précède le début.")
    f = models.RubriqueFixe(salarie_id=salarie.id, code=rub.code, montant=montant, date_debut=date_debut, date_fin=date_fin,
                            commentaire=(commentaire or None), cree_par=acteur.identifiant)
    db.add(f)
    db.flush()
    return f
