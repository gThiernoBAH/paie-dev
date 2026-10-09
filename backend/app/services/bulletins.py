"""Préparation, calcul et validation des bulletins d'une campagne."""
import calendar
import dataclasses
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core import models
from ..moteur import calcul
from ..moteur.arrondis import centimes
from ..moteur.modeles import EntreeBulletin, ParametresPaie, Rubrique
from ..moteur.parametres_paie import charger
from . import parametres as param
from . import conges as svc_conges
from . import discipline as svc_discipline
from . import rubriques_fixes as svc_fixes
from . import prets as svc_prets
from . import presences as svc_presences
from . import salaries as svc_salaries


class ErreurPaie(Exception):
    """Erreur de gestion affichable telle quelle (code HTTP suggéré dans .statut)."""
    def __init__(self, message: str, statut: int = 409):
        super().__init__(message)
        self.statut = statut


# ----------------------------------------------------------------- sérialisation
def vers_json(obj: Any) -> Any:
    """Decimal -> texte exact, dates -> ISO, dataclasses -> dict (pour figer entrées et paramètres)."""
    if isinstance(obj, Decimal):
        return format(obj, "f")
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: vers_json(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): vers_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [vers_json(v) for v in obj]
    return obj


def lignes_vers_json(lignes) -> list:
    return [{"code": l.code, "libelle": l.libelle, "type": l.type,
             "quantite": None if l.quantite is None else format(l.quantite, "f"),
             "taux": None if l.taux is None else format(l.taux, "f"), "montant": format(l.montant, "f")} for l in lignes]


# ----------------------------------------------------------------- périmètre d'une campagne
def jours_payes_par_defaut(salarie: models.Salarie, campagne: models.Campagne) -> Decimal:
    """30 pour un mois entier ; sinon nombre de jours calendaires entre entrée et sortie dans la période."""
    debut = max(campagne.debut, salarie.date_embauche or campagne.debut)
    fin = min(campagne.fin, salarie.date_sortie or campagne.fin)
    if debut > fin:
        return Decimal(0)
    if debut == campagne.debut and fin == campagne.fin:
        return Decimal(30)
    return Decimal(min(30, (fin - debut).days + 1))


def salaries_eligibles(db: Session, campagne: models.Campagne) -> list:
    q = db.query(models.Salarie).filter(
        or_(models.Salarie.date_embauche.is_(None), models.Salarie.date_embauche <= campagne.fin),
        or_(models.Salarie.date_sortie.is_(None), models.Salarie.date_sortie >= campagne.debut),
    )
    if campagne.type_campagne == "mensuelle":
        return q.filter(models.Salarie.type_remuneration == "mensuel").order_by(models.Salarie.matricule).all()
    if campagne.type_campagne == "journaliere":
        ids = {p.salarie_id for p in db.query(models.Pointage.salarie_id).filter(
            models.Pointage.jour >= campagne.debut, models.Pointage.jour <= campagne.fin).distinct().all()}
        return [s for s in q.filter(models.Salarie.type_remuneration == "journalier").order_by(models.Salarie.matricule).all() if s.id in ids]
    return []


def initialiser(db: Session, campagne: models.Campagne, acteur: models.Utilisateur) -> int:
    """Ajoute à la campagne les salariés concernés (sans toucher à ceux déjà présents)."""
    deja = {p.salarie_id for p in db.query(models.PresencePeriode).filter_by(campagne_id=campagne.id).all()}
    ajoutes = 0
    for s in salaries_eligibles(db, campagne):
        if s.id in deja:
            continue
        db.add(models.PresencePeriode(
            campagne_id=campagne.id, salarie_id=s.id, jours_payes=jours_payes_par_defaut(s, campagne),
            source="manuel", modifie_par=acteur.identifiant))
        ajoutes += 1
    db.flush()
    return ajoutes


def presences_depuis_pointages(db: Session, campagne: models.Campagne, acteur: models.Utilisateur, ecraser_manuel: bool = False) -> dict:
    """Remplit heures et jours de présence à partir des pointages (absences : saisie à la main)."""
    resume = {"mises_a_jour": 0, "ignorees_manuel": 0, "incompletes": 0, "absences_proposees": {}}
    for pr in db.query(models.PresencePeriode).filter_by(campagne_id=campagne.id).all():
        if pr.source == "manuel" and not ecraser_manuel and (pr.jours_presence or pr.heures_travaillees or pr.hs1 or pr.hs2 or pr.hs3 or pr.hs4):
            resume["ignorees_manuel"] += 1
            continue
        s = pr.salarie
        r = svc_presences.calculer(db, s, campagne.debut, campagne.fin)
        pr.jours_presence, pr.heures_travaillees = Decimal(r.jours_presence), r.heures_normales
        eligible = s.eligible_heures_sup
        pr.hs1, pr.hs2, pr.hs3, pr.hs4 = (r.heures_sup[i] if eligible else Decimal(0) for i in (1, 2, 3, 4))
        pr.source, pr.modifie_par, pr.modifie_le = "pointage", acteur.identifiant, datetime.now(timezone.utc)
        resume["mises_a_jour"] += 1
        resume["incompletes"] += len(r.jours_sans_sortie)
        if r.absences_detectees and param.lire(db, "pointage_absences_automatiques", campagne.fin):
            resume["absences_proposees"][s.matricule] = [j.isoformat() for j in r.absences_detectees]
    db.flush()
    return resume


# ----------------------------------------------------------------- calcul
def _identite(s: models.Salarie) -> dict:
    ref = lambda r: None if r is None else {"code": r.code, "libelle": r.libelle}
    return {
        "matricule": s.matricule, "nom": s.nom, "prenoms": s.prenoms, "sexe": s.sexe,
        "date_naissance": vers_json(s.date_naissance), "date_embauche": vers_json(s.date_embauche),
        "situation_matrimoniale": s.situation_matrimoniale, "nombre_enfants": s.nombre_enfants,
        "parts": float(s.nombre_parts), "type_remuneration": s.type_remuneration,
        "mode_paiement": s.mode_paiement, "emploi": ref(s.emploi), "service": ref(s.service),
        "categorie": ref(s.categorie), "site": ref(s.site), "banque": ref(s.banque),
    }


def _rubriques_conges(db: Session, campagne: models.Campagne, salarie: models.Salarie, salaire) -> list:
    """Mode « indemnité de congés » : les jours de congé annuel approuvés du mois sortent du salaire de base
    (ligne CGR) et sont payés par une indemnité (ligne ICP), valorisée à salaire mensuel ÷ jours de référence,
    majorée du pourcentage paramétré. En mode « maintien du salaire » (défaut), le bulletin n'est pas touché."""
    if campagne.type_campagne != "mensuelle" or campagne.nature_bulletin != "mensuel":
        return []
    if param.lire(db, "conges_mode_paiement", campagne.fin) != "indemnite_conges":
        return []
    jours = Decimal(0)
    for c in db.query(models.Conge).filter(models.Conge.salarie_id == salarie.id, models.Conge.type_conge == "annuel",
                                           models.Conge.statut == "approuve", models.Conge.debut <= campagne.fin,
                                           models.Conge.fin >= campagne.debut).all():
        jours += svc_conges.jours_ouvrables(db, max(c.debut, campagne.debut), min(c.fin, campagne.fin))
    if jours <= 0:
        return []
    base = Decimal(str(param.lire(db, "conges_jours_base_mensuelle", campagne.fin)))
    majoration = Decimal(str(param.lire(db, "conges_majoration_indemnite", campagne.fin)))
    retenue = centimes((Decimal(salaire.montant) + Decimal(salaire.sursalaire or 0)) * jours / base)
    indemnite = centimes(retenue * (Decimal(100) + majoration) / Decimal(100))
    return [Rubrique("CGR", "Congés payés pris (retenue sur salaire)", "RI", retenue, jours),
            Rubrique("ICP", "Indemnité de congés payés", "GI", indemnite, jours)]


def construire_entree(db: Session, campagne: models.Campagne, salarie: models.Salarie, presence: models.PresencePeriode) -> EntreeBulletin:
    salaire = svc_salaries.salaire_en_vigueur(salarie, campagne.fin)
    if salaire is None:
        raise ErreurPaie(f"{salarie.matricule} : aucun salaire en vigueur au {campagne.fin.strftime('%d/%m/%Y')}.")
    journalier = campagne.nature_bulletin == "journalier"
    saisies = db.query(models.SaisieRubrique).filter_by(campagne_id=campagne.id, salarie_id=salarie.id).order_by(models.SaisieRubrique.id).all()
    cmu_journaliers = param.lire(db, "cmu_applicable_journaliers", campagne.fin)
    # Mise à pied (sans solde) : jours ouvrés couverts = absences non payées, bulletins mensuels seulement.
    mise_a_pied = svc_discipline.jours_mise_a_pied(db, salarie.id, campagne.debut, campagne.fin) if not journalier else Decimal(0)
    jours_ja = min(Decimal(31), Decimal(presence.jours_absence_ja or 0) + mise_a_pied)
    # Rubriques fixes du salarié (bulletins mensuels de campagne mensuelle) puis rubriques propres au mode de paiement des congés.
    fixes = svc_fixes.rubriques_du_mois(db, salarie.id, campagne.debut, campagne.fin) \
        if (campagne.type_campagne == "mensuelle" and not journalier) else []
    supplementaires = tuple(fixes) + tuple(_rubriques_conges(db, campagne, salarie, salaire))
    return EntreeBulletin(
        nature=campagne.nature_bulletin, debut=campagne.debut, fin=campagne.fin, parts=Decimal(salarie.nombre_parts),
        personnes_cmu=0 if (journalier and not cmu_journaliers) else salarie.nombre_personnes_cmu,
        date_entree=salarie.date_embauche, salaire_categoriel=salaire.montant, sursalaire=salaire.sursalaire,
        jours_payes=presence.jours_payes, jours_absence_ja=jours_ja, heures_absence=presence.heures_absence,
        indemnite_transport=salarie.indemnite_transport, heures_travaillees=presence.heures_travaillees,
        jours_presence=presence.jours_presence,
        heures_sup={1: presence.hs1, 2: presence.hs2, 3: presence.hs3, 4: presence.hs4},
        rubriques=supplementaires + tuple(Rubrique(s.code, s.libelle, s.type, s.montant, s.quantite) for s in saisies),
    )


def calculer_un(db: Session, campagne: models.Campagne, presence: models.PresencePeriode, params: Optional[ParametresPaie] = None) -> models.Bulletin:
    if campagne.statut in ("validee", "cloturee"):
        raise ErreurPaie("La campagne est validée : ses bulletins ne peuvent plus être recalculés.")
    salarie = presence.salarie
    if params is None:
        svc_prets.appliquer(db, campagne, salarie.id)
    params = params or charger(db, campagne.fin)
    entree = construire_entree(db, campagne, salarie, presence)
    r = calcul.calculer_bulletin(entree, params)
    champs = dict(
        identite=_identite(salarie), entree=vers_json(entree), parametres=vers_json(params), lignes=lignes_vers_json(r.lignes),
        total_imposable_brut=r.total_imposable_brut, total_retenues_imposables=r.total_retenues_imposables,
        total_imposable=r.total_imposable, cnps=r.cnps, its=r.its, total_impots=r.total_impots,
        gains_non_imposables=r.gains_non_imposables, retenues_non_imposables=r.retenues_non_imposables,
        net_non_imposable=r.net_non_imposable, net_a_payer=r.net_a_payer,
        charges_patronales=vers_json(r.charges_patronales), anomalies=r.anomalies, calcule_le=datetime.now(timezone.utc),
    )
    b = db.query(models.Bulletin).filter_by(campagne_id=campagne.id, salarie_id=salarie.id).first()
    if b is None:
        b = models.Bulletin(campagne_id=campagne.id, salarie_id=salarie.id, statut="brouillon", **champs)
        db.add(b)
    else:
        for k, v in champs.items():
            setattr(b, k, v)
    db.flush()
    return b


def calculer_campagne(db: Session, campagne: models.Campagne) -> dict:
    if campagne.statut in ("validee", "cloturee"):
        raise ErreurPaie("La campagne est validée : ses bulletins ne peuvent plus être recalculés.")
    svc_prets.appliquer(db, campagne)
    params = charger(db, campagne.fin)
    resume = {"calcules": 0, "erreurs": [], "anomalies": 0}
    for presence in db.query(models.PresencePeriode).filter_by(campagne_id=campagne.id).all():
        try:
            b = calculer_un(db, campagne, presence, params)
            resume["calcules"] += 1
            resume["anomalies"] += 1 if b.anomalies else 0
        except ErreurPaie as e:
            resume["erreurs"].append({"matricule": presence.salarie.matricule, "motif": str(e)})
    # des bulletins d'un salarié retiré de la campagne ne doivent pas subsister
    ids = {p.salarie_id for p in db.query(models.PresencePeriode).filter_by(campagne_id=campagne.id).all()}
    for b in db.query(models.Bulletin).filter_by(campagne_id=campagne.id, statut="brouillon").all():
        if b.salarie_id not in ids:
            db.delete(b)
    if resume["calcules"]:
        campagne.statut = "calculee"
    db.flush()
    return resume


# ----------------------------------------------------------------- validation
def verifier_validation(db: Session, campagne: models.Campagne) -> list:
    """Liste des raisons qui empêchent de valider (vide = on peut valider)."""
    raisons = []
    if campagne.statut not in ("calculee",):
        raisons.append("La campagne doit être calculée avant d'être validée." if campagne.statut == "ouverte" else "La campagne est déjà validée.")
        return raisons
    nb_presences = db.query(models.PresencePeriode).filter_by(campagne_id=campagne.id).count()
    bulletins = db.query(models.Bulletin).filter_by(campagne_id=campagne.id).all()
    if len(bulletins) != nb_presences:
        raisons.append("Des salariés de la campagne n'ont pas de bulletin calculé : recalculez la campagne.")
    for b in bulletins:
        if b.anomalies:
            raisons.append(f"{b.identite['matricule']} : " + " ".join(b.anomalies))
    if param.lire(db, "validation_bloquee_si_a_confirmer", campagne.fin):
        a_confirmer = param.critiques_a_confirmer(db, campagne.fin)
        if a_confirmer:
            raisons.append("Paramètres critiques à confirmer : " + ", ".join(p.libelle for p in a_confirmer) + ".")
    return raisons


def valider(db: Session, campagne: models.Campagne, acteur: models.Utilisateur) -> int:
    raisons = verifier_validation(db, campagne)
    if raisons:
        raise ErreurPaie("Validation impossible : " + " | ".join(raisons))
    maintenant = datetime.now(timezone.utc)
    n = 0
    for b in db.query(models.Bulletin).filter_by(campagne_id=campagne.id).all():
        b.statut, b.valide_par, b.valide_le = "valide", acteur.identifiant, maintenant
        n += 1
    campagne.statut, campagne.valide_par, campagne.valide_le = "validee", acteur.identifiant, maintenant
    svc_prets.marquer_preleve(db, campagne)
    db.flush()
    return n


def rouvrir(db: Session, campagne: models.Campagne) -> None:
    """Déverrouillage exceptionnel (administrateur, motif tracé) : les bulletins repassent en brouillon."""
    if campagne.statut == "cloturee":
        raise ErreurPaie("Une campagne clôturée ne peut plus être rouverte.")
    if campagne.statut != "validee":
        raise ErreurPaie("Seule une campagne validée peut être rouverte.")
    from sqlalchemy import text
    db.execute(text("SET LOCAL paie.deverrouillage = 'on'"))
    for b in db.query(models.Bulletin).filter_by(campagne_id=campagne.id).all():
        b.statut, b.valide_par, b.valide_le = "brouillon", None, None
    campagne.statut, campagne.valide_par, campagne.valide_le = "calculee", None, None
    svc_prets.remettre_a_prevoir(db, campagne)
    db.flush()
