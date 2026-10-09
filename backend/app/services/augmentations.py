"""Augmentations de salaire en masse : aperçu (rien n'est écrit), application par lot, annulation du lot."""
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from sqlalchemy.orm import Session

from ..core import models
from . import exercices as svc_ex
from . import salaries as svc_salaries

D = Decimal
ARRONDIS = {1, 5, 10, 50, 100}


class ErreurAugmentation(ValueError):
    pass


def _arrondir(v: Decimal, pas: int) -> Decimal:
    return (v / pas).quantize(D(1), rounding=ROUND_HALF_UP) * pas


def _majorer(valeur: Decimal, mode: str, taux: Decimal, pas: int) -> Decimal:
    nouveau = valeur * (D(100) + taux) / D(100) if mode == "pourcentage" else valeur + taux
    return _arrondir(max(D(0), nouveau), pas)


def selectionner(db: Session, filtres: dict) -> list:
    """Salariés en activité visés par les filtres (service, section, emploi, catégorie, contrat, rémunération, liste de matricules)."""
    q = db.query(models.Salarie).filter(models.Salarie.est_actif.is_(True))
    for champ in ("service_id", "section_id", "emploi_id", "categorie_id", "type_contrat_id", "site_id"):
        if filtres.get(champ):
            q = q.filter(getattr(models.Salarie, champ) == filtres[champ])
    if filtres.get("type_remuneration"):
        q = q.filter(models.Salarie.type_remuneration == filtres["type_remuneration"])
    if filtres.get("salarie_ids"):
        q = q.filter(models.Salarie.id.in_(filtres["salarie_ids"]))
    return q.order_by(models.Salarie.matricule).all()


def apercu(db: Session, filtres: dict, mode: str, valeur: Decimal, cible: str, date_effet, arrondi: int = 1) -> dict:
    if mode not in ("pourcentage", "montant"):
        raise ErreurAugmentation("Mode inconnu.")
    if cible not in ("salaire", "sursalaire", "les_deux"):
        raise ErreurAugmentation("Cible inconnue.")
    if arrondi not in ARRONDIS:
        raise ErreurAugmentation("Arrondi inconnu.")
    if mode == "montant" and cible == "les_deux":
        raise ErreurAugmentation("Un montant fixe s'applique au salaire catégoriel ou au sursalaire, pas aux deux.")
    lignes, ignores, total = [], [], D(0)
    for s in selectionner(db, filtres):
        nom = f"{s.nom} {s.prenoms or ''}".strip()
        actuel = svc_salaries.salaire_en_vigueur(s, date_effet)
        if actuel is None:
            ignores.append({"matricule": s.matricule, "nom": nom, "motif": "Aucun salaire en vigueur à cette date."})
            continue
        if any(e.date_effet == date_effet for e in s.evolutions):
            ignores.append({"matricule": s.matricule, "nom": nom, "motif": "Un salaire existe déjà à cette date d'effet."})
            continue
        if any(e.date_effet > date_effet for e in s.evolutions):
            ignores.append({"matricule": s.matricule, "nom": nom, "motif": "Un salaire plus récent existe déjà : l'historique ne se réécrit pas."})
            continue
        montant, sur = D(actuel.montant), D(actuel.sursalaire or 0)
        n_montant = _majorer(montant, mode, valeur, arrondi) if cible in ("salaire", "les_deux") else montant
        n_sur = _majorer(sur, mode, valeur, arrondi) if (cible in ("sursalaire", "les_deux") and sur > 0) else sur
        if cible == "sursalaire" and sur == 0 and mode == "montant":
            n_sur = _arrondir(valeur, arrondi)
        delta = (n_montant + n_sur) - (montant + sur)
        total += delta
        lignes.append({"salarie_id": s.id, "matricule": s.matricule, "nom": nom,
                       "ancien_salaire": montant, "ancien_sursalaire": sur, "nouveau_salaire": n_montant, "nouveau_sursalaire": n_sur,
                       "difference": delta})
    return {"lignes": lignes, "ignores": ignores, "nombre": len(lignes), "total_mensuel": total, "total_annuel": total * 12}


def appliquer(db: Session, libelle: str, filtres: dict, mode: str, valeur: Decimal, cible: str, date_effet, arrondi: int,
              acteur: models.Utilisateur) -> models.LotAugmentation:
    interdit = svc_ex.message_si_cloture(db, date_effet)
    if interdit:
        raise ErreurAugmentation(interdit)
    a = apercu(db, filtres, mode, valeur, cible, date_effet, arrondi)
    if not a["lignes"]:
        raise ErreurAugmentation("Aucun salarié concerné : rien à appliquer.")
    lot = models.LotAugmentation(libelle=libelle, date_effet=date_effet, mode=mode, valeur=valeur, cible=cible, filtres=filtres,
                                 nb_salaries=a["nombre"], total_mensuel=a["total_mensuel"], cree_par=acteur.identifiant)
    db.add(lot)
    db.flush()
    for l in a["lignes"]:
        db.add(models.EvolutionSalaire(salarie_id=l["salarie_id"], date_effet=date_effet, montant=l["nouveau_salaire"],
                                       sursalaire=l["nouveau_sursalaire"], motif=f"Augmentation : {libelle}"[:200],
                                       cree_par=acteur.identifiant, lot_id=lot.id))
    db.flush()
    return lot


def annuler(db: Session, lot: models.LotAugmentation, acteur: models.Utilisateur) -> int:
    """Supprime les évolutions du lot, à condition qu'aucune paie validée ne couvre déjà la date d'effet."""
    if lot.statut != "applique":
        raise ErreurAugmentation("Ce lot est déjà annulé.")
    interdit = svc_ex.message_si_cloture(db, lot.date_effet)
    if interdit:
        raise ErreurAugmentation(interdit)
    deja = db.query(models.Campagne).filter(models.Campagne.statut.in_(("validee", "cloturee")), models.Campagne.fin >= lot.date_effet).first()
    if deja is not None:
        raise ErreurAugmentation(f"Annulation impossible : la paie « {deja.libelle} » est déjà validée à partir de la date d'effet.")
    evolutions = db.query(models.EvolutionSalaire).filter_by(lot_id=lot.id).all()
    for e in evolutions:
        db.delete(e)
    lot.statut, lot.annule_par, lot.annule_le = "annule", acteur.identifiant, datetime.now(timezone.utc)
    db.flush()
    return len(evolutions)
