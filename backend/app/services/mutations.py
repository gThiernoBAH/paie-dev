"""Historique des mutations d'un salarié : affectation (service, section, emploi, catégorie, site…) et salaire."""
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from ..core import models

# champ de la fiche -> nature enregistrée
SUIVIS = {
    "service_id": "service", "section_id": "section", "emploi_id": "emploi", "categorie_id": "categorie",
    "site_id": "site", "type_contrat_id": "type_contrat", "type_remuneration": "type_remuneration",
}
LIBELLES_NATURE = {
    "service": "Service", "section": "Section", "emploi": "Emploi", "categorie": "Catégorie", "site": "Site",
    "type_contrat": "Type de contrat", "type_remuneration": "Mode de rémunération", "salaire": "Salaire",
    "embauche": "Embauche", "sortie": "Départ",
}
REMUNERATION = {"mensuel": "Mensuel", "journalier": "Journalier"}


def _etiquette(db: Session, champ: str, valeur) -> Optional[str]:
    if valeur is None or valeur == "":
        return None
    if champ == "type_remuneration":
        return REMUNERATION.get(valeur, str(valeur))
    r = db.get(models.Referentiel, valeur)
    return r.libelle if r is not None else None


def instantane(db: Session, s: models.Salarie) -> dict:
    """Valeurs actuelles des champs suivis, à capturer AVANT une modification de la fiche."""
    return {champ: getattr(s, champ) for champ in SUIVIS}


def enregistrer_changements(db: Session, s: models.Salarie, avant: dict, date_effet: Optional[date], motif: Optional[str],
                            acteur: models.Utilisateur) -> list:
    """Crée une ligne d'historique par champ suivi dont la valeur a changé ; renvoie les natures modifiées."""
    natures = []
    for champ, nature in SUIVIS.items():
        ancien, nouveau = avant.get(champ), getattr(s, champ)
        if ancien == nouveau:
            continue
        db.add(models.MutationSalarie(
            salarie_id=s.id, date_effet=date_effet or date.today(), nature=nature,
            ancienne_valeur=_etiquette(db, champ, ancien), nouvelle_valeur=_etiquette(db, champ, nouveau),
            motif=(motif or None), cree_par=acteur.identifiant))
        natures.append(nature)
    return natures


def _f(montant, sursalaire) -> str:
    texte = f"{float(montant):,.0f}".replace(",", " ") + " F"
    if sursalaire and float(sursalaire):
        texte += f" + {float(sursalaire):,.0f}".replace(",", " ") + " F de sursalaire"
    return texte


def historique(db: Session, s: models.Salarie, avec_salaire: bool) -> list:
    """Frise chronologique (la plus récente d'abord) : embauche, mutations, évolutions de salaire, départ."""
    lignes = []
    if s.date_embauche:
        lignes.append({"date": s.date_embauche, "nature": "embauche", "libelle": LIBELLES_NATURE["embauche"], "avant": None,
                       "apres": None, "motif": None, "par": None, "ordre": 0})
    for m in db.query(models.MutationSalarie).filter_by(salarie_id=s.id).all():
        lignes.append({"date": m.date_effet, "nature": m.nature, "libelle": LIBELLES_NATURE.get(m.nature, m.nature),
                       "avant": m.ancienne_valeur, "apres": m.nouvelle_valeur, "motif": m.motif, "par": m.cree_par, "ordre": 1})
    if avec_salaire:
        precedent = None
        for e in sorted(s.evolutions, key=lambda x: x.date_effet):
            lignes.append({"date": e.date_effet, "nature": "salaire", "libelle": LIBELLES_NATURE["salaire"],
                           "avant": None if precedent is None else _f(precedent.montant, precedent.sursalaire),
                           "apres": _f(e.montant, e.sursalaire), "motif": e.motif, "par": e.cree_par, "ordre": 1})
            precedent = e
    if s.date_sortie:
        lignes.append({"date": s.date_sortie, "nature": "sortie", "libelle": LIBELLES_NATURE["sortie"], "avant": None,
                       "apres": None, "motif": s.motif_sortie, "par": None, "ordre": 2})
    lignes.sort(key=lambda x: (x["date"], x["ordre"]), reverse=True)
    for l in lignes:
        del l["ordre"]
    return lignes
