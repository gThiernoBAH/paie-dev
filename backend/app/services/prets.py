"""Prêts et avances sur salaire : échéancier et prélèvement sur les bulletins."""
from decimal import ROUND_DOWN, Decimal
from typing import Optional

from sqlalchemy.orm import Session

from ..core import models

ORIGINE = "pret"
CODE_RUBRIQUE = "PRE"


def creer(db: Session, s: models.Salarie, type_pret: str, libelle: str, montant: Decimal, nombre: int,
          annee: int, mois: int, acteur: models.Utilisateur) -> models.Pret:
    """Échéances mensuelles égales (arrondies au franc) ; la dernière absorbe le reliquat."""
    pret = models.Pret(salarie_id=s.id, type_pret=type_pret, libelle=libelle, montant=montant,
                       nombre_echeances=nombre, cree_par=acteur.identifiant)
    base = (montant / nombre).quantize(Decimal(1), rounding=ROUND_DOWN)
    a, m = annee, mois
    for i in range(nombre):
        du = base if i < nombre - 1 else montant - base * (nombre - 1)
        pret.echeances.append(models.EcheancePret(annee=a, mois=m, montant=du))
        m += 1
        if m == 13:
            a, m = a + 1, 1
    db.add(pret)
    db.flush()
    return pret


def reste_a_rembourser(pret: models.Pret) -> Decimal:
    return sum((e.montant for e in pret.echeances if e.statut == "prevue"), Decimal(0))


def annuler(db: Session, pret: models.Pret) -> None:
    for e in pret.echeances:
        if e.statut == "prevue":
            e.statut, e.campagne_id = "annulee", None
    pret.statut = "annule"
    db.flush()


def appliquer(db: Session, campagne: models.Campagne, salarie_id: Optional[int] = None) -> int:
    """(Re)génère les saisies de remboursement d'une campagne à partir des échéances dues.

    Mensuelle / journalière n°1 : échéances du mois et arriérés. Solde de tout compte : tout le reste dû.
    Idempotent : les anciennes saisies de prêt de la campagne sont remplacées."""
    if campagne.statut in ("validee", "cloturee"):
        return 0
    q = db.query(models.SaisieRubrique).filter_by(campagne_id=campagne.id, origine=ORIGINE)
    if salarie_id:
        q = q.filter_by(salarie_id=salarie_id)
    q.delete()
    for e in db.query(models.EcheancePret).filter_by(campagne_id=campagne.id, statut="prevue").all():
        if not salarie_id or e.pret.salarie_id == salarie_id:
            e.campagne_id = None
    db.flush()
    if campagne.type_campagne == "exceptionnelle" or (campagne.type_campagne == "journaliere" and campagne.numero > 1):
        return 0
    presents = {p.salarie_id for p in db.query(models.PresencePeriode).filter_by(campagne_id=campagne.id).all()}
    if salarie_id:
        presents &= {salarie_id}
    n = 0
    for pret in db.query(models.Pret).filter(models.Pret.statut == "actif", models.Pret.salarie_id.in_(presents or {0})).all():
        dues = [e for e in pret.echeances if e.statut == "prevue" and (
            campagne.type_campagne == "solde" or (e.annee, e.mois) <= (campagne.annee, campagne.mois))]
        if not dues:
            continue
        total = sum((e.montant for e in dues), Decimal(0))
        for e in dues:
            e.campagne_id = campagne.id
        db.add(models.SaisieRubrique(
            campagne_id=campagne.id, salarie_id=pret.salarie_id, code=CODE_RUBRIQUE,
            libelle=f"Remboursement {pret.libelle}"[:100], type="RN", montant=total, origine=ORIGINE,
            reference_id=pret.id, commentaire=f"{len(dues)} échéance(s)", cree_par="système"))
        n += 1
    db.flush()
    return n


def marquer_preleve(db: Session, campagne: models.Campagne) -> None:
    for e in db.query(models.EcheancePret).filter_by(campagne_id=campagne.id, statut="prevue").all():
        e.statut = "prelevee"
        if all(x.statut != "prevue" for x in e.pret.echeances):
            e.pret.statut = "solde"
    db.flush()


def remettre_a_prevoir(db: Session, campagne: models.Campagne) -> None:
    for e in db.query(models.EcheancePret).filter_by(campagne_id=campagne.id, statut="prelevee").all():
        e.statut = "prevue"
        if e.pret.statut == "solde":
            e.pret.statut = "actif"
    db.flush()
