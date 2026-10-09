"""Prêts et avances sur salaire : échéancier et prélèvement sur les bulletins."""
from datetime import date
from decimal import ROUND_DOWN, Decimal
from typing import Optional

from sqlalchemy.orm import Session

from ..core import models
from . import exercices as svc_ex

ORIGINE = "pret"
CODE_RUBRIQUE = "PRE"

MOTIFS_CLOTURE = {"depart": "Départ du salarié", "demission": "Démission", "deces": "Décès",
                  "licenciement": "Licenciement", "autre": "Autre motif"}
ISSUES = {"regularise": "Solde régularisé hors paie", "abandon": "Passé en perte (irrécouvrable)"}
MODES_REGLEMENT = {"especes": "Espèces", "cheque": "Chèque", "virement": "Virement", "autre": "Autre"}


class ErreurPret(ValueError):
    """Message en français, affichable tel quel."""


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


# ----------------------------------------------------------------- règlement manuel et clôture
def montant_regle(pret: models.Pret) -> Decimal:
    """Déjà remboursé : prélevé sur la paie ou réglé hors paie."""
    return sum((e.montant for e in pret.echeances if e.statut in ("prelevee", "reglee")), Decimal(0))


def montant_abandonne(pret: models.Pret) -> Decimal:
    return sum((e.montant for e in pret.echeances if e.statut == "abandonnee"), Decimal(0))


def _detacher(db: Session, e: models.EcheancePret, touchees: dict) -> None:
    """Retire l'échéance d'une campagne non validée ; la campagne sera régénérée (saisie PRE) par l'appelant."""
    if e.campagne_id:
        c = db.get(models.Campagne, e.campagne_id)
        if c is not None and c.statut in ("ouverte", "calculee"):
            touchees[c.id] = c
        e.campagne_id = None


def _regenerer(db: Session, touchees: dict, salarie_id: int) -> list:
    """Régénère les retenues de prêt des campagnes touchées ; renvoie les campagnes à recalculer."""
    a_recalculer = []
    for c in touchees.values():
        appliquer(db, c, salarie_id)
        if c.statut == "calculee":
            a_recalculer.append(c.libelle)
    return a_recalculer


def _solder_si_fini(pret: models.Pret) -> None:
    if pret.statut == "actif" and all(e.statut != "prevue" for e in pret.echeances):
        pret.statut = "solde"


def regler_echeance(db: Session, pret: models.Pret, e: models.EcheancePret, date_reglement: date, mode: str,
                    commentaire: Optional[str], acteur: models.Utilisateur) -> list:
    """Marque une échéance comme réglée hors paie : elle ne sera plus retenue sur les bulletins."""
    if pret.statut != "actif":
        raise ErreurPret("Ce prêt n'est plus actif.")
    interdit = svc_ex.message_si_cloture(db, date_reglement)
    if interdit:
        raise ErreurPret(interdit)
    if e.pret_id != pret.id:
        raise ErreurPret("Échéance étrangère à ce prêt.")
    if e.statut != "prevue":
        raise ErreurPret("Seule une échéance « prévue » peut être marquée comme réglée.")
    if mode not in MODES_REGLEMENT:
        raise ErreurPret("Mode de règlement inconnu.")
    touchees: dict = {}
    _detacher(db, e, touchees)
    e.statut, e.date_reglement, e.mode_reglement = "reglee", date_reglement, mode
    e.regle_par, e.commentaire = acteur.identifiant, (commentaire or None)
    db.flush()
    _solder_si_fini(pret)
    db.flush()
    return _regenerer(db, touchees, pret.salarie_id)


def rouvrir_echeance(db: Session, pret: models.Pret, e: models.EcheancePret) -> None:
    """Annule un règlement manuel saisi par erreur (les prélèvements sur paie ne sont jamais défaits ici)."""
    if pret.statut == "cloture":
        raise ErreurPret("Ce prêt est clôturé : ses échéances ne peuvent plus être modifiées.")
    if e.pret_id != pret.id or e.statut != "reglee":
        raise ErreurPret("Seul un règlement manuel peut être annulé.")
    e.statut, e.date_reglement, e.mode_reglement, e.regle_par, e.commentaire = "prevue", None, None, None, None
    if pret.statut == "solde":
        pret.statut = "actif"
    db.flush()


def cloturer(db: Session, pret: models.Pret, motif: str, issue: str, date_cloture: date, commentaire: Optional[str],
             acteur: models.Utilisateur) -> list:
    """Clôture anticipée d'un prêt jamais remboursé en totalité (départ surprise, démission, décès…).

    Le reste dû est soit régularisé hors paie, soit passé en perte ; dans les deux cas les échéances restantes
    quittent les campagnes et le prêt ne produit plus aucune retenue."""
    if pret.statut != "actif":
        raise ErreurPret("Seul un prêt actif peut être clôturé.")
    interdit = svc_ex.message_si_cloture(db, date_cloture)
    if interdit:
        raise ErreurPret(interdit)
    if motif not in MOTIFS_CLOTURE:
        raise ErreurPret("Motif de clôture inconnu.")
    if issue not in ISSUES:
        raise ErreurPret("Issue de clôture inconnue.")
    restantes = [e for e in pret.echeances if e.statut == "prevue"]
    if not restantes:
        raise ErreurPret("Il ne reste aucune échéance à clôturer.")
    touchees: dict = {}
    for e in restantes:
        _detacher(db, e, touchees)
        if issue == "regularise":
            e.statut, e.date_reglement, e.mode_reglement, e.regle_par = "reglee", date_cloture, "autre", acteur.identifiant
        else:
            e.statut = "abandonnee"
        e.commentaire = f"Clôture : {MOTIFS_CLOTURE[motif]}"[:200]
    pret.statut, pret.date_cloture, pret.motif_cloture, pret.issue_cloture = "cloture", date_cloture, motif, issue
    pret.commentaire_cloture, pret.cloture_par = (commentaire or None), acteur.identifiant
    db.flush()
    return _regenerer(db, touchees, pret.salarie_id)
