"""Virements de paie : préparation du lot, contrôle, lancement."""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from ..core import crypto, models
from .bulletins import ErreurPaie


def preparer(db: Session, campagne: models.Campagne, acteur: models.Utilisateur, date_valeur: Optional[date] = None) -> models.LotVirement:
    if campagne.statut not in ("validee", "cloturee"):
        raise ErreurPaie("La campagne doit être validée avant de préparer les virements.")
    actif = db.query(models.LotVirement).filter(models.LotVirement.campagne_id == campagne.id,
                                                models.LotVirement.statut.in_(("prepare", "lance"))).first()
    if actif:
        raise ErreurPaie("Un lot de virement existe déjà pour cette campagne (annulez-le s'il n'est pas encore lancé).")
    lot = models.LotVirement(campagne_id=campagne.id, libelle=f"Salaires – {campagne.libelle}"[:120], date_valeur=date_valeur,
                             cree_par=acteur.identifiant)
    exclus, total = [], Decimal(0)
    for b in db.query(models.Bulletin).filter_by(campagne_id=campagne.id, statut="valide").order_by(models.Bulletin.id).all():
        s = db.get(models.Salarie, b.salarie_id)
        ident = f"{s.matricule} {s.nom}"
        if b.net_a_payer <= 0:
            exclus.append({"matricule": s.matricule, "nom": ident, "motif": "Net à payer nul ou négatif", "montant": str(b.net_a_payer)})
        elif s.mode_paiement != "virement":
            exclus.append({"matricule": s.matricule, "nom": ident, "motif": f"Paiement par {s.mode_paiement or 'mode non renseigné'}", "montant": str(b.net_a_payer)})
        elif not s.rib_chiffre:
            exclus.append({"matricule": s.matricule, "nom": ident, "motif": "RIB manquant", "montant": str(b.net_a_payer)})
        else:
            lot.ordres.append(models.OrdreVirement(salarie_id=s.id, bulletin_id=b.id, montant=b.net_a_payer,
                                                   banque=s.banque.libelle if s.banque else None, rib_chiffre=s.rib_chiffre))
            total += b.net_a_payer
    lot.nombre_ordres, lot.total, lot.exclus = len(lot.ordres), total, exclus
    if not lot.ordres:
        raise ErreurPaie("Aucun virement à émettre : " + (f"{len(exclus)} salarié(s) exclu(s) (RIB manquant, espèces...)." if exclus else "aucun bulletin validé."))
    db.add(lot)
    db.flush()
    return lot


def annuler(db: Session, lot: models.LotVirement) -> None:
    if lot.statut != "prepare":
        raise ErreurPaie("Seul un lot préparé, non lancé, peut être annulé.")
    lot.statut = "annule"
    db.flush()


def lancer(db: Session, lot: models.LotVirement, acteur: models.Utilisateur) -> None:
    if lot.statut != "prepare":
        raise ErreurPaie("Ce lot n'est pas en attente de lancement.")
    lot.statut, lot.lance_par, lot.lance_le = "lance", acteur.identifiant, datetime.now(timezone.utc)
    db.flush()


def lignes_export(db: Session, lot: models.LotVirement, campagne: models.Campagne) -> tuple[list, list]:
    """Entêtes et lignes du fichier de virement (RIB en clair : l'appelant trace l'accès)."""
    entetes = ["Matricule", "Nom et prénoms", "Banque", "RIB", "Montant (FCFA)", "Libellé"]
    motif = f"SALAIRE {campagne.mois:02d}/{campagne.annee}" + (f" N{campagne.numero}" if campagne.numero > 1 else "")
    lignes = []
    for o in lot.ordres:
        s = o.salarie
        lignes.append([s.matricule, f"{s.nom} {s.prenoms or ''}".strip(), o.banque or "", crypto.dechiffrer(o.rib_chiffre), o.montant, motif])
    return entetes, lignes
